"""
Модуль загрузки и предварительной обработки данных Bitcoin.

Считывает CSV-файл, приводит столбцы к единому формату,
сортирует данные по дате (по возрастанию).
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_data(filepath: str | Path) -> pd.DataFrame:
    """Загружает CSV-файл с историческими данными Bitcoin.

    Parameters
    ----------
    filepath : str | Path
        Путь к CSV-файлу с данными.

    Returns
    -------
    pd.DataFrame
        DataFrame с колонками: Date, Open, High, Low, Close, Volume.
        Индекс — порядковый, данные отсортированы по Date (возрастание).
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Файл не найден: {filepath}")

    logger.info("Загрузка данных из %s", filepath)
    df = pd.read_csv(filepath)

    # Унификация имени столбца с датой
    if "Start" in df.columns:
        df = df.rename(columns={"Start": "Date"})
    if "Date" not in df.columns:
        raise ValueError("Не найден столбец 'Date' или 'Start' в данных.")

    df["Date"] = pd.to_datetime(df["Date"])

    # Оставляем только нужные столбцы
    required_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Отсутствуют столбцы: {missing}")

    df = df[required_cols].copy()

    # Сортировка по дате (по возрастанию)
    df = df.sort_values("Date").reset_index(drop=True)

    logger.info("Загружено %d записей. Период: %s — %s",
                len(df), df["Date"].min().date(), df["Date"].max().date())
    return df
