"""
Модуль разделения данных на train/test.

Разделение по времени (без перемешивания): 50 % train, 50 % test.
"""

import logging
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def split_data(
    df: pd.DataFrame,
    train_ratio: float = 0.5,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Разделяет DataFrame на train и test по времени.

    Parameters
    ----------
    df : pd.DataFrame
        Полный набор данных (отсортированный по дате).
    train_ratio : float
        Доля обучающей выборки (по умолчанию 0.5).

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame]
        (train_df, test_df) — без перемешивания.
    """
    split_idx = int(len(df) * train_ratio)
    train_df = df.iloc[:split_idx].copy().reset_index(drop=True)
    test_df = df.iloc[split_idx:].copy().reset_index(drop=True)

    logger.info(
        "Разделение: train=%d строк, test=%d строк (ratio=%.2f)",
        len(train_df), len(test_df), train_ratio,
    )
    return train_df, test_df
