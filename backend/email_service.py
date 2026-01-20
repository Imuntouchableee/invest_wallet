"""
Сервис отправки email для восстановления пароля
"""

import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta


# Конфигурация SMTP (можно заменить на свой сервер)
# Для тестирования используется Gmail
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = "your_email@gmail.com"  # Замените на ваш email
SMTP_PASSWORD = "your_app_password"  # Замените на пароль приложения


def generate_recovery_code():
    """Генерирует 6-значный код восстановления"""
    return ''.join(random.choices(string.digits, k=6))


def send_recovery_email(to_email, code):
    """
    Отправляет email с кодом восстановления
    
    Args:
        to_email: Email получателя
        code: 6-значный код восстановления
    
    Returns:
        bool: True если отправлено успешно, False если ошибка
    """
    try:
        # Создаем сообщение
        msg = MIMEMultipart('alternative')
        msg['Subject'] = '🔐 Код восстановления пароля - Invest Wallet'
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email
        
        # HTML версия письма
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #0a0e17;
                    color: #ffffff;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 500px;
                    margin: 0 auto;
                    background: linear-gradient(135deg, #121828 0%, #1a2236 100%);
                    border-radius: 16px;
                    padding: 40px;
                    border: 1px solid #00d4ff33;
                    box-shadow: 0 20px 60px rgba(0, 212, 255, 0.1);
                }}
                .logo {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .logo h1 {{
                    color: #00d4ff;
                    font-size: 28px;
                    margin: 0;
                }}
                .logo span {{
                    color: #00ff88;
                }}
                .title {{
                    text-align: center;
                    color: #ffffff;
                    font-size: 20px;
                    margin-bottom: 20px;
                }}
                .code-box {{
                    background: linear-gradient(135deg, #00d4ff22 0%, #00ff8822 100%);
                    border: 2px solid #00d4ff;
                    border-radius: 12px;
                    padding: 25px;
                    text-align: center;
                    margin: 25px 0;
                }}
                .code {{
                    font-size: 42px;
                    font-weight: bold;
                    color: #00d4ff;
                    letter-spacing: 10px;
                    font-family: 'Courier New', monospace;
                }}
                .info {{
                    color: #8a93a7;
                    font-size: 14px;
                    text-align: center;
                    line-height: 1.6;
                }}
                .warning {{
                    background: #ff336622;
                    border: 1px solid #ff3366;
                    border-radius: 8px;
                    padding: 15px;
                    margin-top: 20px;
                    color: #ff6688;
                    font-size: 13px;
                    text-align: center;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    color: #4a5568;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="logo">
                    <h1>💼 Invest <span>Wallet</span></h1>
                </div>
                
                <div class="title">
                    Восстановление пароля
                </div>
                
                <p class="info">
                    Вы запросили восстановление пароля для вашего аккаунта.<br>
                    Используйте код ниже для подтверждения:
                </p>
                
                <div class="code-box">
                    <div class="code">{code}</div>
                </div>
                
                <p class="info">
                    Код действителен в течение <strong>10 минут</strong>.<br>
                    Введите его в приложении для продолжения.
                </p>
                
                <div class="warning">
                    ⚠️ Если вы не запрашивали восстановление пароля,<br>
                    проигнорируйте это письмо или обратитесь в поддержку.
                </div>
                
                <div class="footer">
                    © 2024 Invest Wallet. Все права защищены.<br>
                    Это автоматическое сообщение, не отвечайте на него.
                </div>
            </div>
        </body>
        </html>
        """
        
        # Текстовая версия
        text = f"""
        Invest Wallet - Восстановление пароля
        
        Ваш код восстановления: {code}
        
        Код действителен 10 минут.
        
        Если вы не запрашивали восстановление пароля, проигнорируйте это письмо.
        """
        
        part1 = MIMEText(text, 'plain', 'utf-8')
        part2 = MIMEText(html, 'html', 'utf-8')
        
        msg.attach(part1)
        msg.attach(part2)
        
        # Отправляем
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        
        print(f"✅ Email отправлен на {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки email: {e}")
        return False


def verify_recovery_code(stored_code, stored_expires, entered_code):
    """
    Проверяет код восстановления
    
    Args:
        stored_code: Код из базы данных
        stored_expires: Время истечения кода
        entered_code: Введенный пользователем код
    
    Returns:
        tuple: (bool успех, str сообщение)
    """
    if not stored_code or not stored_expires:
        return False, "Код восстановления не запрашивался"
    
    if datetime.now() > stored_expires:
        return False, "Код восстановления истёк"
    
    if stored_code != entered_code:
        return False, "Неверный код восстановления"
    
    return True, "Код подтверждён"


def get_code_expiry_time(minutes=10):
    """Возвращает время истечения кода"""
    return datetime.now() + timedelta(minutes=minutes)


# Для тестирования без реальной отправки email
def send_recovery_email_mock(to_email, code):
    """
    Мок-функция для тестирования (не отправляет реальный email)
    Просто выводит код в консоль
    """
    print(f"""
    ╔══════════════════════════════════════════════╗
    ║        ТЕСТОВЫЙ РЕЖИМ (БЕЗ ОТПРАВКИ)         ║
    ╠══════════════════════════════════════════════╣
    ║  Email: {to_email:<35}  ║
    ║  Код восстановления: {code}                  ║
    ╚══════════════════════════════════════════════╝
    """)
    return True
