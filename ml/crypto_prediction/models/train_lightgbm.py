"""
Обучение моделей LightGBM (регрессия + классификация) с оптимизацией Optuna.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import numpy as np
import optuna
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor

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
    """Целевая функция Optuna для LGBMRegressor (минимизация RMSE)."""
    params: Dict[str, Any] = {
        "num_leaves": trial.suggest_int("num_leaves", 20, 150),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000, step=50),
        "max_depth": trial.suggest_int("max_depth", 3, 12),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "random_state": 42,
        "verbosity": -1,
    }
    model = LGBMRegressor(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
    )
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
    """Целевая функция Optuna для LGBMClassifier (максимизация accuracy)."""
    params: Dict[str, Any] = {
        "num_leaves": trial.suggest_int("num_leaves", 20, 150),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000, step=50),
        "max_depth": trial.suggest_int("max_depth", 3, 12),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "random_state": 42,
        "verbosity": -1,
    }
    model = LGBMClassifier(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
    )
    acc = float(model.score(X_val, y_val))
    return acc


def train_lightgbm(
    X_train: pd.DataFrame,
    y_train_price: pd.Series,
    y_train_dir: pd.Series,
    X_test: pd.DataFrame,
    y_test_price: pd.Series,
    y_test_dir: pd.Series,
    n_trials: int = 50,
) -> Tuple[LGBMRegressor, LGBMClassifier]:
    """Обучает LightGBM-модели с оптимизацией гиперпараметров Optuna.

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
    Tuple[LGBMRegressor, LGBMClassifier]
        Обученные модели.
    """
    logger.info("=== Оптимизация LGBMRegressor (Optuna, %d trials) ===", n_trials)
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
    best_reg_params["verbosity"] = -1
    logger.info("Лучшие параметры регрессора: %s", best_reg_params)

    reg_model = LGBMRegressor(**best_reg_params)
    reg_model.fit(X_train, y_train_price)

    logger.info("=== Оптимизация LGBMClassifier (Optuna, %d trials) ===", n_trials)
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
    best_clf_params["verbosity"] = -1
    logger.info("Лучшие параметры классификатора: %s", best_clf_params)

    clf_model = LGBMClassifier(**best_clf_params)
    clf_model.fit(X_train, y_train_dir)

    # Сохранение
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(reg_model, SAVE_DIR / "lightgbm_regressor.joblib")
    joblib.dump(clf_model, SAVE_DIR / "lightgbm_classifier.joblib")
    logger.info("Модели LightGBM сохранены в %s", SAVE_DIR)

    return reg_model, clf_model
