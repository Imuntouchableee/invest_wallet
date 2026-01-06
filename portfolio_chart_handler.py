"""
Профессиональный обработчик портфельного графика
Создает серьезный и информативный график за 7 дней
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from models import session, PortfolioHistory
import io


def create_portfolio_chart(user_id, output_file=None):
    """
    Создает серьезный профессиональный график портфеля за 7 дней
    """
    
    # Получаем историю за 7 дней
    seven_days_ago = datetime.now() - timedelta(days=7)
    history = session.query(PortfolioHistory).filter(
        PortfolioHistory.user_id == user_id,
        PortfolioHistory.timestamp >= seven_days_ago
    ).order_by(PortfolioHistory.timestamp).all()
    
    if not history or len(history) < 2:
        print("Недостаточно данных для графика")
        return None
    
    timestamps = [h.timestamp for h in history]
    values = [h.portfolio_value for h in history]
    
    # Вычисляем статистику
    min_val = min(values)
    max_val = max(values)
    current_val = values[-1]
    initial_val = values[0]
    change = current_val - initial_val
    change_pct = (change / initial_val * 100) if initial_val > 0 else 0
    
    # Создаем фигуру
    fig = plt.figure(figsize=(16, 10), dpi=100)
    fig.patch.set_facecolor('#0F1419')
    
    # Создаем подграфик (без нижней панели статистики)
    ax = fig.add_axes([0.08, 0.10, 0.9, 0.78])
    ax.set_facecolor('#1A1F2E')
    
    # === ОСНОВНОЙ ГРАФИК ===
    ax.plot(timestamps, values, color='#00D4FF', linewidth=3, label='Стоимость портфеля', zorder=3)
    ax.fill_between(timestamps, values, alpha=0.2, color='#00D4FF', zorder=2)
    
    # === КЛЮЧЕВЫЕ ТОЧКИ ===
    max_idx = values.index(max_val)
    min_idx = values.index(min_val)
    
    # Максимум
    ax.plot(timestamps[max_idx], max_val, 'o', color='#00FF88', markersize=12, zorder=5, label='Максимум')
    ax.annotate(f'MAX: {max_val:.2f} RUB', 
                xy=(timestamps[max_idx], max_val),
                xytext=(0, 15), textcoords='offset points',
                ha='center', fontsize=10, weight='bold',
                color='#00FF88',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#1A1F2E', edgecolor='#00FF88', linewidth=2),
                arrowprops=dict(arrowstyle='->', color='#00FF88', lw=1.5))
    
    # Минимум
    ax.plot(timestamps[min_idx], min_val, 'o', color='#FF3366', markersize=12, zorder=5, label='Минимум')
    ax.annotate(f'MIN: {min_val:.2f} RUB', 
                xy=(timestamps[min_idx], min_val),
                xytext=(0, -25), textcoords='offset points',
                ha='center', fontsize=10, weight='bold',
                color='#FF3366',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#1A1F2E', edgecolor='#FF3366', linewidth=2),
                arrowprops=dict(arrowstyle='->', color='#FF3366', lw=1.5))
    
    # Текущее
    ax.plot(timestamps[-1], current_val, 's', color='#FFD700', markersize=12, zorder=5, label='Текущее')
    
    # === ДНЕВНЫЕ РАЗДЕЛИТЕЛИ ===
    current_date = timestamps[0].date()
    for ts in timestamps:
        if ts.date() != current_date:
            ax.axvline(x=ts, color='#3A4050', linestyle='--', alpha=0.4, linewidth=1.5, zorder=1)
            current_date = ts.date()
    
    # === СЕТКА ===
    ax.grid(True, alpha=0.15, color='#FFF', linestyle=':', linewidth=0.8)
    ax.set_axisbelow(True)
    
    # === ОФОРМЛЕНИЕ ОСЕЙ ===
    for spine in ax.spines.values():
        spine.set_color('#3A4050')
        spine.set_linewidth(2)
    
    ax.tick_params(colors='#A0A8B8', labelsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m\n%H:%M'))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.0f}'))
    
    ax.set_xlabel('Дата и время (UTC+3)', fontsize=11, color='#A0A8B8', weight='bold')
    ax.set_ylabel('Стоимость портфеля, RUB', fontsize=11, color='#A0A8B8', weight='bold')
    
    # === ЛЕГЕНДА ===
    ax.legend(loc='upper left', framealpha=0.95, facecolor='#1A1F2E',
              edgecolor='#3A4050', labelcolor='#A0A8B8', fontsize=10, frameon=True)
    
    # === ЗАГОЛОВОК ===
    title_color = '#00FF88' if change >= 0 else '#FF3366'
    title_text = f'ПОРТФЕЛЬ: {current_val:.2f} RUB | {change:+.2f} RUB ({change_pct:+.1f}%)'
    plt.title(title_text, fontsize=15, color=title_color, weight='bold', pad=20, family='monospace')
    
    # Дата генерации
    gen_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    fig.text(0.98, 0.005, f'Сгенерировано: {gen_time}', fontsize=8,
            color='#7A8290', ha='right', style='italic')
    
    plt.tight_layout(rect=[0, 0.02, 1, 0.95])
    
    # Сохраняем
    if output_file:
        plt.savefig(output_file, facecolor='#0F1419', edgecolor='none',
                   dpi=100, bbox_inches='tight', pad_inches=0.5)
        plt.close(fig)
        print(f"График сохранен: {output_file}")
        return output_file
    else:
        buf = io.BytesIO()
        plt.savefig(buf, format='png', facecolor='#0F1419', edgecolor='none',
                   dpi=100, bbox_inches='tight', pad_inches=0.5)
        buf.seek(0)
        plt.close(fig)
        return buf


def get_chart_stats(user_id):
    """Возвращает статистику портфеля"""
    seven_days_ago = datetime.now() - timedelta(days=7)
    history = session.query(PortfolioHistory).filter(
        PortfolioHistory.user_id == user_id,
        PortfolioHistory.timestamp >= seven_days_ago
    ).order_by(PortfolioHistory.timestamp).all()
    
    if not history:
        return None
    
    values = [h.portfolio_value for h in history]
    
    return {
        'current': values[-1],
        'initial': values[0],
        'max': max(values),
        'min': min(values),
        'change': values[-1] - values[0],
        'change_percent': ((values[-1] - values[0]) / values[0] * 100) if values[0] > 0 else 0,
        'count': len(history),
    }


if __name__ == "__main__":
    print("Тестирование графика...")
    chart_file = create_portfolio_chart(1, output_file='portfolio_chart_test.png')
    stats = get_chart_stats(1)
    if stats:
        print(f"Текущее: {stats['current']:.2f} RUB")
        print(f"Начало: {stats['initial']:.2f} RUB")
        print(f"Изменение: {stats['change']:+.2f} RUB ({stats['change_percent']:+.1f}%)")
    print("Готово!")
