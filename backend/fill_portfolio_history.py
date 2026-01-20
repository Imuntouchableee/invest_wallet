"""
Скрипт для заполнения таблицы portfolio_history корректными данными за 7 дней
"""

from datetime import datetime, timedelta
from backend.models import session, PortfolioHistory, User, Asset
import random

def clear_and_fill_portfolio_history(user_id=1):
    """Очищает старые данные и заполняет корректными за 7 дней"""
    
    # Очищаем старые данные
    session.query(PortfolioHistory).filter(PortfolioHistory.user_id == user_id).delete()
    session.commit()
    print("✓ Таблица portfolio_history очищена")
    
    # Получаем текущий объем портфеля пользователя
    assets = session.query(Asset).filter_by(user_id=user_id).all()
    current_value = sum(a.value_rub for a in assets)
    
    if current_value == 0:
        print("⚠ У пользователя нет активов!")
        return
    
    print(f"📊 Базовая стоимость портфеля: {current_value:.2f} RUB")
    
    # Генерируем данные за 7 дней (168 часов)
    now = datetime.now()
    start_time = now - timedelta(days=7)
    
    # Параметры для реалистичной волатильности
    trend = random.uniform(-0.02, 0.02)  # Общий тренд
    volatility = 0.08  # Волатильность
    
    # Начальное значение (от 70% до 100% текущего объема)
    previous_value = current_value * random.uniform(0.7, 1.0)
    
    records = []
    
    for hour in range(168):  # 168 часов = 7 дней
        timestamp = start_time + timedelta(hours=hour)
        
        # Добавляем трендовое изменение + случайную волатильность
        hour_change_percent = trend / 24 + random.gauss(0, volatility / 24)
        price_change = previous_value * hour_change_percent
        
        # Новое значение портфеля
        current_portfolio_value = previous_value + price_change
        # Ограничиваем минимум на 50% от базовой стоимости
        current_portfolio_value = max(current_portfolio_value, current_value * 0.5)
        
        change = current_portfolio_value - previous_value
        
        record = PortfolioHistory(
            user_id=user_id,
            timestamp=timestamp,
            portfolio_value=round(current_portfolio_value, 2),
            change=round(change, 2),
            daily_change=round(change, 2)
        )
        records.append(record)
        previous_value = current_portfolio_value
    
    # Добавляем все записи
    session.add_all(records)
    session.commit()
    
    print(f"✓ Добавлено {len(records)} записей истории портфеля")
    print(f"  📅 Период: {start_time.strftime('%Y-%m-%d %H:%M')} - {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  💹 Начало: {records[0].portfolio_value:.2f} RUB")
    print(f"  💹 Конец: {records[-1].portfolio_value:.2f} RUB")
    print(f"  📈 Макс: {max(r.portfolio_value for r in records):.2f} RUB")
    print(f"  📉 Мин: {min(r.portfolio_value for r in records):.2f} RUB")


if __name__ == "__main__":
    print("=" * 60)
    print("📝 Заполнение истории портфеля за 7 дней")
    print("=" * 60)
    clear_and_fill_portfolio_history(user_id=1)
    print("\n✅ Готово!")
