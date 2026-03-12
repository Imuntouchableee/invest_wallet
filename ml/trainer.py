"""
Обучение XGBoost-классификатора с оптимизацией гиперпараметров Optuna.

Настройки сохранены из оригинальной реализации:
  - Сэмплер: TPE (Tree-structured Parzen Estimator), Bayesian
  - n_startup_trials: 10 (случайные пробы перед байесовской оптимизацией)
  - multivariate=True (учёт корреляций между гиперпараметрами)
  - Гиперпараметры:
      max_depth         3–10
      learning_rate     0.005–0.3   (log-uniform)
      n_estimators      100–1500    (step 50)
      subsample         0.5–1.0
      colsample_bytree  0.3–1.0
      min_child_weight  1–10
      reg_alpha         1e-8–10.0   (L1, log)
      reg_lambda        1e-8–10.0   (L2, log)
      gamma             1e-8–5.0    (min loss reduction, log)
      scale_pos_weight  0.5–2.0
"""

import logging
import time
from typing import Any, Dict

import numpy as np
import optuna
import pandas as pd
from optuna.samplers import TPESampler
from xgboost import XGBClassifier

optuna.logging.set_verbosity(optuna.logging.WARNING)
logger = logging.getLogger(__name__)


def _create_sampler() -> TPESampler:
    return TPESampler(
        seed=42,
        n_startup_trials=10,
        multivariate=True,
    )


def _objective(
    trial: optuna.Trial,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> float:
    """Целевая функция Optuna для XGBClassifier (максимизация accuracy)."""
    params: Dict[str, Any] = {
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 1500, step=50),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "gamma": trial.suggest_float("gamma", 1e-8, 5.0, log=True),
        "scale_pos_weight": trial.suggest_float("scale_pos_weight", 0.5, 2.0),
        "use_label_encoder": False,
        "eval_metric": "logloss",
        "random_state": 42,
        "verbosity": 0,
    }
    model = XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return float(model.score(X_val, y_val))


def train_xgboost_classifier(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    n_trials: int = 50,
) -> XGBClassifier:
    """Обучает XGBoost-классификатор с оптимизацией Optuna.

    Parameters
    ----------
    X_train, X_val : pd.DataFrame
        Признаки обучающей и валидационной выборок.
    y_train, y_val : pd.Series
        Целевая переменная (0/1 — падение/рост).
    n_trials : int
        Количество итераций Optuna (по умолчанию 50).

    Returns
    -------
    XGBClassifier
        Обученная модель.
    """
    logger.info("XGBoost: байесовская оптимизация (TPE, %d trials)...", n_trials)
    t0 = time.perf_counter()

    study = optuna.create_study(direction="maximize", sampler=_create_sampler())
    study.optimize(
        lambda trial: _objective(trial, X_train, y_train, X_val, y_val),
        n_trials=n_trials,
        show_progress_bar=False,
    )

    best_params = study.best_params
    best_params.update({
        "random_state": 42,
        "verbosity": 0,
        "use_label_encoder": False,
        "eval_metric": "logloss",
    })

    logger.info(
        "Оптимизация завершена за %.1f сек. Лучший Accuracy: %.4f",
        time.perf_counter() - t0,
        study.best_value,
    )
    logger.info("Лучшие параметры: %s", best_params)

    clf = XGBClassifier(**best_params)
    clf.fit(X_train, y_train)
    return clf
