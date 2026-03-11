"""
Обучение моделей CatBoost (регрессия + классификация) с оптимизацией Optuna.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import numpy as np
import optuna
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor

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
    """Целевая функция Optuna для CatBoostRegressor (минимизация RMSE)."""
    params: Dict[str, Any] = {
        "depth": trial.suggest_int("depth", 4, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "iterations": trial.suggest_int("iterations", 100, 1000, step=50),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
        "random_state": 42,
        "verbose": 0,
    }
    model = CatBoostRegressor(**params)
    model.fit(X_train, y_train, eval_set=(X_val, y_val), verbose=0)
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
    """Целевая функция Optuna для CatBoostClassifier (максимизация accuracy)."""
    params: Dict[str, Any] = {
        "depth": trial.suggest_int("depth", 4, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "iterations": trial.suggest_int("iterations", 100, 1000, step=50),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
        "random_state": 42,
        "verbose": 0,
    }
    model = CatBoostClassifier(**params)
    model.fit(X_train, y_train, eval_set=(X_val, y_val), verbose=0)
    acc = float(model.score(X_val, y_val))
    return acc


def train_catboost(
    X_train: pd.DataFrame,
    y_train_price: pd.Series,
    y_train_dir: pd.Series,
    X_test: pd.DataFrame,
    y_test_price: pd.Series,
    y_test_dir: pd.Series,
    n_trials: int = 50,
) -> Tuple[CatBoostRegressor, CatBoostClassifier]:
    """Обучает CatBoost-модели с оптимизацией гиперпараметров Optuna.

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
    Tuple[CatBoostRegressor, CatBoostClassifier]
        Обученные модели.
    """
    logger.info("=== Оптимизация CatBoostRegressor (Optuna, %d trials) ===", n_trials)
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
    best_reg_params["verbose"] = 0
    logger.info("Лучшие параметры регрессора: %s", best_reg_params)

    reg_model = CatBoostRegressor(**best_reg_params)
    reg_model.fit(X_train, y_train_price, verbose=0)

    logger.info("=== Оптимизация CatBoostClassifier (Optuna, %d trials) ===", n_trials)
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
    best_clf_params["verbose"] = 0
    logger.info("Лучшие параметры классификатора: %s", best_clf_params)

    clf_model = CatBoostClassifier(**best_clf_params)
    clf_model.fit(X_train, y_train_dir, verbose=0)

    # Сохранение
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(reg_model, SAVE_DIR / "catboost_regressor.joblib")
    joblib.dump(clf_model, SAVE_DIR / "catboost_classifier.joblib")
    logger.info("Модели CatBoost сохранены в %s", SAVE_DIR)

    return reg_model, clf_model
