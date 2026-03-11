#!/usr/bin/env python3
"""
main.py — точка входа проекта прогнозирования цены Bitcoin.

Запуск:
    python main.py

Последовательность:
    1. Загрузка данных
    2. Feature engineering
    3. Разделение train / test (50/50)
    4. Обучение XGBoost, LightGBM, CatBoost (Optuna)
    5. Benchmark (метрики + время)
    6. Предсказание на следующий день
    7. Сохранение результатов
"""

import logging
import sys
from pathlib import Path

import pandas as pd

# ── Добавляем корневую директорию проекта в sys.path ──────────────
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.benchmark import run_benchmark
from features.feature_engineering import (
    FEATURE_COLUMNS,
    build_features,
    get_feature_target_split,
)
from models.train_catboost import train_catboost
from models.train_lightgbm import train_lightgbm
from models.train_xgboost import train_xgboost
from predict.predict import predict_next_day, print_predictions
from utils.data_loader import load_data
from utils.splitter import split_data

# ── Настройка логирования ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# ── Пути ──────────────────────────────────────────────────────────
DATA_PATH = PROJECT_ROOT / "data" / "btc_prices.csv"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_PATH = RESULTS_DIR / "model_metrics.csv"

N_TRIALS = 50


def main() -> None:
    """Главная функция: полный пайплайн обучения и оценки."""
    logger.info("=" * 60)
    logger.info("  СТАРТ: Прогнозирование цены Bitcoin")
    logger.info("=" * 60)

    # 1. Загрузка данных
    logger.info("Шаг 1/7: Загрузка данных")
    df_raw = load_data(DATA_PATH)

    # 2. Feature engineering
    logger.info("Шаг 2/7: Генерация признаков")
    df = build_features(df_raw)

    # 3. Разделение
    logger.info("Шаг 3/7: Разделение данных (50/50)")
    train_df, test_df = split_data(df, train_ratio=0.5)

    X_train, y_train_price, y_train_dir = get_feature_target_split(train_df)
    X_test, y_test_price, y_test_dir = get_feature_target_split(test_df)

    logger.info("Признаки (%d): %s", len(X_train.columns), list(X_train.columns))

    # 4. Обучение моделей
    logger.info("Шаг 4/7: Обучение моделей")

    logger.info("─── XGBoost ───")
    train_xgboost(
        X_train, y_train_price, y_train_dir,
        X_test, y_test_price, y_test_dir,
        n_trials=N_TRIALS,
    )

    logger.info("─── LightGBM ───")
    train_lightgbm(
        X_train, y_train_price, y_train_dir,
        X_test, y_test_price, y_test_dir,
        n_trials=N_TRIALS,
    )

    logger.info("─── CatBoost ───")
    train_catboost(
        X_train, y_train_price, y_train_dir,
        X_test, y_test_price, y_test_dir,
        n_trials=N_TRIALS,
    )

    # 5. Benchmark
    logger.info("Шаг 5/7: Бенчмарк моделей")
    df_metrics = run_benchmark(X_test, y_test_price, y_test_dir)

    # 6. Вывод результатов
    logger.info("Шаг 6/7: Вывод результатов")
    print("\n")
    print("=" * 90)
    print("  РЕЗУЛЬТАТЫ BENCHMARK")
    print("=" * 90)

    display_cols = [
        "Model", "RMSE", "MAE", "MAPE", "R2",
        "Accuracy", "Precision", "Recall", "F1", "ROC-AUC",
        "prediction_time_seconds",
    ]
    existing_cols = [c for c in display_cols if c in df_metrics.columns]
    print(df_metrics[existing_cols].to_string(index=False))
    print("=" * 90)

    # Сохранение
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df_metrics.to_csv(RESULTS_PATH, index=False)
    logger.info("Метрики сохранены в %s", RESULTS_PATH)

    # 7. Предсказание на следующий день
    logger.info("Шаг 7/7: Предсказание на следующий день")
    X_last = X_test.iloc[[-1]]  # последняя строка test set
    predictions = predict_next_day(X_last)
    print_predictions(predictions)

    logger.info("=" * 60)
    logger.info("  ЗАВЕРШЕНО УСПЕШНО")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
