# Прогнозирование цены Bitcoin (ML)

Проект прогнозирования цены Bitcoin на следующий день с использованием ансамблевых моделей градиентного бустинга: **XGBoost**, **LightGBM** и **CatBoost**.

## Структура проекта

```
crypto_prediction/
├── data/
│   └── btc_prices.csv            # Исторические данные Bitcoin
├── features/
│   └── feature_engineering.py    # Генерация признаков (SMA, EMA, RSI, MACD и др.)
├── models/
│   ├── train_xgboost.py          # Обучение XGBoost + Optuna
│   ├── train_lightgbm.py         # Обучение LightGBM + Optuna
│   ├── train_catboost.py         # Обучение CatBoost + Optuna
│   └── saved/                    # Сохранённые модели (.joblib)
├── evaluation/
│   ├── metrics.py                # Расчёт метрик (MAE, RMSE, Accuracy, ROC-AUC и др.)
│   └── benchmark.py              # Бенчмарк: метрики + время инференса
├── predict/
│   └── predict.py                # Предсказание на следующий день
├── utils/
│   ├── data_loader.py            # Загрузка CSV
│   └── splitter.py               # Разделение train/test
├── results/
│   └── model_metrics.csv         # Итоговые метрики всех моделей
├── main.py                       # Точка входа
├── requirements.txt
└── README.md
```

## Требования

- Python 3.11+
- Библиотеки: см. `requirements.txt`

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
python main.py
```

## Описание пайплайна

1. **Загрузка данных** — чтение CSV, сортировка по дате
2. **Feature Engineering** — создание 23 признаков:
   - Скользящие средние: SMA (7, 14, 30, 60, 200)
   - Экспоненциальные средние: EMA (7, 14, 30)
   - Трендовые индикаторы: RSI(14), MACD, MACD signal, MACD hist
   - Волатильность: rolling std (7, 30)
   - Доходность: return 1d, 3d, 7d
   - Дополнительные: high/low ratio, close/open ratio, volume change
3. **Разделение данных** — 50% train / 50% test (по времени, без перемешивания)
4. **Обучение моделей** — XGBoost, LightGBM, CatBoost с оптимизацией гиперпараметров через Optuna (50 trials)
5. **Оценка качества** — метрики регрессии (MAE, RMSE, MAPE, R²) и классификации (Accuracy, Precision, Recall, F1, ROC-AUC)
6. **Benchmark** — замер времени предсказания
7. **Предсказание** — прогноз цены и вероятности роста/падения на следующий день

## Целевые переменные

| Задача          | Target                                    |
|-----------------|-------------------------------------------|
| Регрессия       | `target_price = Close.shift(-1)`          |
| Классификация   | `target_direction = 1 if Close(t+1) > Close(t) else 0` |

## Результаты

После обучения в консоль выводится сводная таблица:

```
Model       RMSE     MAE     Accuracy     ROC-AUC    prediction_time_seconds
XGBoost     ...      ...     ...          ...        ...
LightGBM    ...      ...     ...          ...        ...
CatBoost    ...      ...     ...          ...        ...
```

Результаты также сохраняются в `results/model_metrics.csv`.

## Автор

Тогузов А. А. — БЭИ2202
