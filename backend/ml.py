class LinearRegression:
    def __init__(self):
        self.k = 0  # наклон (slope)
        self.b = 0  # смещение (bias)

    def fit(self, x, y):
        """Обучение модели на данных (x - время, y - цена)."""
        n = len(x)
        avg_x = sum(x) / n
        avg_y = sum(y) / n

        numerator = sum((x[i] - avg_x) * (y[i] - avg_y) for i in range(n))
        denominator = sum((x[i] - avg_x) ** 2 for i in range(n))

        if denominator == 0:
            self.k = 0
        else:
            self.k = numerator / denominator

        self.b = avg_y - self.k * avg_x

    def predict(self, x):
        """Предсказывает цену для нового значения времени x."""
        return self.k * x + self.b


def predict_future_price(prices):
    # Генерируем "время" как список индексов
    x = list(range(len(prices)))
    y = prices

    model = LinearRegression()
    model.fit(x, y)

    # Предсказываем следующую цену (следующий момент времени)
    next_time = len(prices)
    future_price = model.predict(next_time)

    return round(future_price, 2)
