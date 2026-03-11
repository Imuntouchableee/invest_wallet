"""
Обучение моделей XGBoost (регрессия + классификация) с оптимизацией Optuna.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import numpy as np
import optuna
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

optuna.logging.set_verbosity(optuna.logging.WARNING)
logger = logging.getLogger(__name__)

SAVE_DIR = Path(__file__).parent / "saved"


def _objective_regressor(
    trial: optuna.Trial,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> float:
    """Целевая функция Optuna для XGBRegressor (минимизация RMSE)."""
    params: Dict[str, Any] = {
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000, step=50),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "random_state": 42,
        "verbosity": 0,
    }
    model = XGBRegressor(**params)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    preds = model.predict(X_val)
    rmse = float(np.sqrt(np.mean((y_val.values - preds) ** 2)))
    return rmse


def _objective_classifier(
    trial: optuna.Trial,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> float:
    """Целевая функция Optuna для XGBClassifier (максимизация accuracy)."""
    params: Dict[str, Any] = {
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000, step=50),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "use_label_encoder": False,
        "eval_metric": "logloss",
        "random_state": 42,
        "verbosity": 0,
    }
    model = XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    acc = float(model.score(X_val, y_val))
    return acc


def train_xgboost(
    X_train: pd.DataFrame,
    y_train_price: pd.Series,
    y_train_dir: pd.Series,
    X_test: pd.DataFrame,
    y_test_price: pd.Series,
    y_test_dir: pd.Series,
    n_trials: int = 50,
) -> Tuple[XGBRegressor, XGBClassifier]:
    """Обучает XGBoost-модели с оптимизацией гиперпараметров Optuna.

    Parameters
    ----------
    X_train, X_test : pd.DataFrame
        Признаки.
    y_train_price, y_test_price : pd.Series
        Целевая переменная — цена (регрессия).
    y_train_dir, y_test_dir : pd.Series
        Целевая переменная — направление (классификация).
    n_trials : int
        Количество итераций Optuna.

    Returns
    -------
    Tuple[XGBRegressor, XGBClassifier]
        Обученные модели.
    """
    logger.info("=== Оптимизация XGBRegressor (Optuna, %d trials) ===", n_trials)
    study_reg = optuna.create_study(direction="minimize")
    study_reg.optimize(
        lambda trial: _objective_regressor(
            trial, X_train, y_train_price, X_test, y_test_price,
        ),
        n_trials=n_trials,
        show_progress_bar=False,
    )
    best_reg_params = study_reg.best_params
    best_reg_params["random_state"] = 42
    best_reg_params["verbosity"] = 0
    logger.info("Лучшие параметры регрессора: %s", best_reg_params)

    reg_model = XGBRegressor(**best_reg_params)
    reg_model.fit(X_train, y_train_price)

    logger.info("=== Оптимизация XGBClassifier (Optuna, %d trials) ===", n_trials)
    study_clf = optuna.create_study(direction="maximize")
    study_clf.optimize(
        lambda trial: _objective_classifier(
            trial, X_train, y_train_dir, X_test, y_test_dir,
        ),
        n_trials=n_trials,
        show_progress_bar=False,
    )
    best_clf_params = study_clf.best_params
    best_clf_params["random_state"] = 42
    best_clf_params["verbosity"] = 0
    best_clf_params["use_label_encoder"] = False
    best_clf_params["eval_metric"] = "logloss"
    logger.info("Лучшие параметры классификатора: %s", best_clf_params)

    clf_model = XGBClassifier(**best_clf_params)
    clf_model.fit(X_train, y_train_dir)

    # Сохранение
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(reg_model, SAVE_DIR / "xgboost_regressor.joblib")
    joblib.dump(clf_model, SAVE_DIR / "xgboost_classifier.joblib")
    logger.info("Модели XGBoost сохранены в %s", SAVE_DIR)

    return reg_model, clf_model
