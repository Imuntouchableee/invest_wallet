#!/usr/bin/env python3
"""Скрипт обновления БД при добавлении новых полей"""

import sqlite3
from datetime import datetime

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Проверяем существование таблицы users
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
table_exists = cursor.fetchone() is not None

if table_exists:
    # Получаем список текущих колонок
    cursor.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in cursor.fetchall()}
    
    # Добавляем недостающие колонки
    new_columns = {
        'email': "VARCHAR",
        'phone': "VARCHAR",
        'country': "VARCHAR DEFAULT 'Россия'",
        'full_name': "VARCHAR",
        'avatar_color': "VARCHAR DEFAULT '#00d4ff'",
        'bio': "VARCHAR DEFAULT 'Инвестор криптовалют'",
        'registration_date': "DATETIME DEFAULT CURRENT_TIMESTAMP",
        'last_login': "DATETIME DEFAULT CURRENT_TIMESTAMP",
        'total_trades': "INTEGER DEFAULT 0",
        'total_invested': "REAL DEFAULT 0.0",
        'total_profit': "REAL DEFAULT 0.0",
        'best_asset': "VARCHAR",
        'notification_enabled': "INTEGER DEFAULT 1",
        'dark_theme': "INTEGER DEFAULT 1",
        'two_factor_auth': "INTEGER DEFAULT 0",
    }
    
    for col_name, col_type in new_columns.items():
        if col_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                print(f"✓ Добавлена колонка: {col_name}")
            except Exception as e:
                print(f"⚠ Ошибка добавления {col_name}: {e}")
    
    # Обновляем таблицу assets
    cursor.execute("PRAGMA table_info(assets)")
    asset_columns = {row[1] for row in cursor.fetchall()}
    
    asset_new_columns = {
        'purchase_date': "DATETIME DEFAULT CURRENT_TIMESTAMP",
        'purchase_price': "REAL",
    }
    
    for col_name, col_type in asset_new_columns.items():
        if col_name not in asset_columns:
            try:
                cursor.execute(f"ALTER TABLE assets ADD COLUMN {col_name} {col_type}")
                print(f"✓ Добавлена колонка assets: {col_name}")
            except Exception as e:
                print(f"⚠ Ошибка добавления {col_name}: {e}")

conn.commit()
conn.close()

print("\n✓ Миграция БД завершена успешно!")
