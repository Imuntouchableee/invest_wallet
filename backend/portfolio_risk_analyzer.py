"""
Анализ устойчивости и рисков портфеля
Расчёт индекса стабильности, концентрации, ликвидности и диверсификации
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import statistics

from backend.models import PortfolioHistory, session
from data.database import DatabaseManager

logger = logging.getLogger(__name__)


def _safe_float(value, default=0.0):
    """Безопасное преобразование в float"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class PortfolioRiskAnalyzer:
    """Анализатор рисков портфеля"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.portfolio_history = self._get_portfolio_history()
    
    def _normalize_portfolio_data(self, raw_portfolio: Dict) -> Dict:
        """Преобразует структуру portfolio в нужный формат"""
        # Если уже нормализовано
        if 'assets' in raw_portfolio and 'by_exchange' in raw_portfolio:
            return raw_portfolio
        
        # Если это структура с exchanges и all_assets
        if 'all_assets' in raw_portfolio and 'exchanges' in raw_portfolio:
            by_exchange = {}
            for exchange_name, exchange_data in raw_portfolio['exchanges'].items():
                by_exchange[exchange_name] = exchange_data.get('total_usd', 0.0)
            
            return {
                'assets': raw_portfolio.get('all_assets', []),
                'by_exchange': by_exchange,
                'total_usd': raw_portfolio.get('total_usd', 0.0)
            }
        
        # Если это уже отформатированный портфель
        return raw_portfolio
        
    def _get_portfolio_history(self, days: int = 30) -> List[PortfolioHistory]:
        """Получает историю портфеля за N дней"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            history = session.query(PortfolioHistory).filter(
                PortfolioHistory.user_id == self.user_id,
                PortfolioHistory.timestamp >= cutoff_date
            ).order_by(PortfolioHistory.timestamp).all()
            return history
        except Exception as e:
            logger.error(f"[PORTFOLIO RISK] Error loading history: {e}")
            return []
    
    def calculate_concentration_risk(self, portfolio_data: Dict) -> Dict:
        """
        Анализирует концентрацию портфеля по активам
        Возвращает коэффициент риска (0-100)
        
        Логика:
        - Если 1 актив > 50%, это HIGH_RISK
        - Если 1 актив > 30%, это MEDIUM_RISK
        - Если top3 > 70%, это MEDIUM_RISK
        - Иначе LOW_RISK
        """
        assets = portfolio_data.get('assets', [])
        if not assets:
            return {'risk_level': 'LOW', 'score': 100, 'description': 'Нет данных'}
        
        total_value = sum(a['value_usd'] for a in assets)
        if total_value <= 0:
            return {'risk_level': 'LOW', 'score': 100, 'description': 'Портфель пуст'}
        
        # Вычисляем процент каждого актива
        asset_percentages = []
        for asset in assets:
            pct = (asset['value_usd'] / total_value) * 100
            asset_percentages.append({
                'name': asset['currency'],
                'percentage': pct,
                'value': asset['value_usd']
            })
        
        largest = asset_percentages[0]['percentage'] if asset_percentages else 0
        top3_sum = sum(a['percentage'] for a in asset_percentages[:3]) if len(asset_percentages) >= 3 else sum(a['percentage'] for a in asset_percentages)
        
        # Определяем уровень риска
        if largest > 50:
            risk_level = 'CRITICAL'
            score = max(0, 100 - (largest - 50) * 2)
            description = f"Критическая концентрация: {largest:.1f}% в {asset_percentages[0]['name']}"
        elif largest > 30:
            risk_level = 'HIGH'
            score = max(20, 100 - (largest - 30) * 1.5)
            description = f"Высокая концентрация: {largest:.1f}% в {asset_percentages[0]['name']}"
        elif top3_sum > 70:
            risk_level = 'MEDIUM'
            score = max(40, 100 - (top3_sum - 70) * 0.8)
            description = f"Топ-3 актива составляют {top3_sum:.1f}% портфеля"
        else:
            risk_level = 'LOW'
            score = 85
            description = "Концентрация в норме"
        
        return {
            'risk_level': risk_level,
            'score': score,
            'description': description,
            'largest_asset': asset_percentages[0] if asset_percentages else None,
            'top3_percentage': top3_sum,
            'total_assets': len(asset_percentages),
            'asset_distribution': asset_percentages[:5]  # Топ-5 для отображения
        }
    
    def calculate_exchange_dependency(self, portfolio_data: Dict) -> Dict:
        """
        Анализирует зависимость от одной биржи
        
        Логика:
        - Если одна биржа > 70%, это HIGH_RISK
        - Если одна биржа > 50%, это MEDIUM_RISK
        - Иначе LOW_RISK
        """
        by_exchange = portfolio_data.get('by_exchange', {})
        if not by_exchange:
            return {'risk_level': 'MEDIUM', 'score': 50, 'description': 'Данные недоступны'}
        
        total_value = sum(v for v in by_exchange.values())
        if total_value <= 0:
            return {'risk_level': 'LOW', 'score': 100, 'description': 'Портфель пуст'}
        
        # Вычисляем процент на каждой бирже
        exchange_percentages = []
        for exchange, value in by_exchange.items():
            pct = (value / total_value) * 100
            exchange_percentages.append({
                'exchange': exchange,
                'percentage': pct,
                'value': value
            })
        
        exchange_percentages.sort(key=lambda x: x['percentage'], reverse=True)
        largest_exchange = exchange_percentages[0] if exchange_percentages else None
        largest_pct = largest_exchange['percentage'] if largest_exchange else 0
        
        # Определяем уровень риска
        if largest_pct > 85:
            risk_level = 'CRITICAL'
            score = max(0, 100 - (largest_pct - 85) * 2)
            description = f"Критическая зависимость: {largest_pct:.1f}% на {largest_exchange['exchange']}"
        elif largest_pct > 70:
            risk_level = 'HIGH'
            score = max(20, 100 - (largest_pct - 70) * 1.5)
            description = f"Высокая зависимость от {largest_exchange['exchange']}: {largest_pct:.1f}%"
        elif largest_pct > 50:
            risk_level = 'MEDIUM'
            score = max(40, 100 - (largest_pct - 50))
            description = f"Умеренная зависимость: {largest_pct:.1f}% на одной бирже"
        else:
            risk_level = 'LOW'
            score = 90
            description = "Портфель распределён нормально"
        
        return {
            'risk_level': risk_level,
            'score': score,
            'description': description,
            'exchanges': exchange_percentages,
            'largest_exchange': largest_exchange
        }
    
    def calculate_volatility_risk(self) -> Dict:
        """
        Анализирует волатильность портфеля по истории
        Смотрит стандартное отклонение изменений портфеля
        """
        if len(self.portfolio_history) < 3:
            return {
                'risk_level': 'UNKNOWN',
                'score': 50,
                'description': 'Недостаточно данных для анализа',
                'days_tracked': len(self.portfolio_history)
            }
        
        # Вычисляем дневные изменения
        daily_changes = []
        for i in range(1, len(self.portfolio_history)):
            prev_value = _safe_float(self.portfolio_history[i-1].total_value_usd)
            curr_value = _safe_float(self.portfolio_history[i].total_value_usd)
            
            if prev_value > 0:
                change_pct = ((curr_value - prev_value) / prev_value) * 100
                daily_changes.append(change_pct)
        
        if not daily_changes:
            return {
                'risk_level': 'LOW',
                'score': 85,
                'description': 'Портфель стабилен (нет данных об изменениях)',
                'days_tracked': len(self.portfolio_history)
            }
        
        # Вычисляем стандартное отклонение (волатильность)
        try:
            volatility = statistics.stdev(daily_changes) if len(daily_changes) > 1 else 0
        except:
            volatility = 0
        
        avg_change = statistics.mean(daily_changes)
        
        # Определяем уровень риска
        if volatility > 5:
            risk_level = 'HIGH'
            score = max(20, 100 - volatility * 5)
        elif volatility > 2:
            risk_level = 'MEDIUM'
            score = max(40, 100 - volatility * 8)
        else:
            risk_level = 'LOW'
            score = 85
        
        return {
            'risk_level': risk_level,
            'score': score,
            'description': f"Волатильность: {volatility:.2f}% (σ)",
            'volatility': volatility,
            'avg_daily_change': avg_change,
            'max_change': max(daily_changes),
            'min_change': min(daily_changes),
            'days_tracked': len(daily_changes)
        }
    
    def calculate_stablecoin_ratio(self, portfolio_data: Dict) -> Dict:
        """
        Анализирует долю стейблкоинов в портфеле
        Больше стейблкоинов = меньше риск, но меньше потенциал
        """
        STABLECOINS = {'USDT', 'USDC', 'USD', 'BUSD', 'DAI', 'TUSD'}
        
        assets = portfolio_data.get('assets', [])
        total_value = sum(a['value_usd'] for a in assets)
        
        if total_value <= 0:
            return {
                'risk_level': 'NEUTRAL',
                'score': 50,
                'description': 'Портфель пуст',
                'stablecoin_percentage': 0
            }
        
        stablecoin_value = sum(
            a['value_usd'] for a in assets
            if a['currency'].upper() in STABLECOINS
        )
        stablecoin_pct = (stablecoin_value / total_value) * 100
        
        if stablecoin_pct > 80:
            risk_level = 'SAFE_BUT_CONSERVATIVE'
            score = 70
            description = f"Высокая доля стейблкоинов ({stablecoin_pct:.1f}%) - консервативный портфель"
        elif stablecoin_pct > 50:
            risk_level = 'MODERATE'
            score = 75
            description = f"Значительная доля стейблкоинов ({stablecoin_pct:.1f}%)"
        elif stablecoin_pct > 20:
            risk_level = 'BALANCED'
            score = 80
            description = f"Оптимальная доля стейблкоинов ({stablecoin_pct:.1f}%)"
        else:
            risk_level = 'AGGRESSIVE'
            score = 60
            description = f"Минимальная доля стейблкоинов ({stablecoin_pct:.1f}%) - агрессивный портфель"
        
        return {
            'risk_level': risk_level,
            'score': score,
            'description': description,
            'stablecoin_percentage': stablecoin_pct,
            'stablecoin_value': stablecoin_value,
            'risky_assets_percentage': 100 - stablecoin_pct
        }
    
    def calculate_liquidity_risk(self, portfolio_data: Dict) -> Dict:
        """
        Анализирует риск ликвидности портфеля
        Маленькие монеты или малоизвестные = высокий риск ликвидности
        """
        assets = portfolio_data.get('assets', [])
        total_value = sum(a['value_usd'] for a in assets)
        
        if total_value <= 0:
            return {
                'risk_level': 'NEUTRAL',
                'score': 50,
                'description': 'Портфель пуст',
                'low_liquidity_percentage': 0
            }
        
        # Активы < $100 в пропорции считаем низколиквидными
        low_liquidity_value = sum(
            a['value_usd'] for a in assets
            if a['value_usd'] < 100
        )
        low_liquidity_pct = (low_liquidity_value / total_value) * 100
        
        if low_liquidity_pct > 40:
            risk_level = 'HIGH'
            score = max(10, 100 - low_liquidity_pct)
            description = f"Высокий риск ликвидности: {low_liquidity_pct:.1f}% в позициях < $100"
        elif low_liquidity_pct > 20:
            risk_level = 'MEDIUM'
            score = max(40, 100 - low_liquidity_pct * 1.5)
            description = f"Умеренный риск ликвидности: {low_liquidity_pct:.1f}% в малых позициях"
        else:
            risk_level = 'LOW'
            score = 85
            description = "Портфель состоит из ликвидных активов"
        
        return {
            'risk_level': risk_level,
            'score': score,
            'description': description,
            'low_liquidity_percentage': low_liquidity_pct,
            'small_positions_count': sum(1 for a in assets if a['value_usd'] < 100),
            'illiquid_value': low_liquidity_value
        }
    
    def calculate_overall_stability_score(self, portfolio_data: Dict) -> Dict:
        """
        Вычисляет общий индекс устойчивости портфеля (0-100)
        Комбинирует все риски
        """
        # Нормализуем данные
        normalized_portfolio = self._normalize_portfolio_data(portfolio_data)
        
        concentration = self.calculate_concentration_risk(normalized_portfolio)
        exchange_dep = self.calculate_exchange_dependency(normalized_portfolio)
        volatility = self.calculate_volatility_risk()
        stablecoin = self.calculate_stablecoin_ratio(normalized_portfolio)
        liquidity = self.calculate_liquidity_risk(normalized_portfolio)
        
        # Взвешенное среднее
        weights = {
            'concentration': 0.25,
            'exchange_dependency': 0.20,
            'volatility': 0.20,
            'stablecoin': 0.15,
            'liquidity': 0.20
        }
        
        overall_score = (
            concentration['score'] * weights['concentration'] +
            exchange_dep['score'] * weights['exchange_dependency'] +
            volatility['score'] * weights['volatility'] +
            stablecoin['score'] * weights['stablecoin'] +
            liquidity['score'] * weights['liquidity']
        )
        
        # Определяем уровень
        if overall_score >= 80:
            stability_level = 'EXCELLENT'
            emoji = '🟢'
        elif overall_score >= 65:
            stability_level = 'GOOD'
            emoji = '🟡'
        elif overall_score >= 50:
            stability_level = 'MODERATE'
            emoji = '🟠'
        else:
            stability_level = 'POOR'
            emoji = '🔴'
        
        # Выявляем主要 риск
        risks = [
            ('concentration', concentration),
            ('exchange_dependency', exchange_dep),
            ('volatility', volatility),
            ('liquidity', liquidity)
        ]
        main_risk = min(risks, key=lambda x: x[1]['score'])
        
        # Рекомендация
        recommendation = self._get_recommendation(
            concentration, exchange_dep, volatility, stablecoin, liquidity
        )
        
        return {
            'stability_score': round(overall_score, 1),
            'stability_level': stability_level,
            'emoji': emoji,
            'recommendation': recommendation,
            'main_risk': {
                'name': main_risk[0],
                'score': main_risk[1]['score'],
                'description': main_risk[1]['description']
            },
            'metrics': {
                'concentration': concentration,
                'exchange_dependency': exchange_dep,
                'volatility': volatility,
                'stablecoin': stablecoin,
                'liquidity': liquidity
            }
        }
    
    def _get_recommendation(self, concentration, exchange_dep, volatility, stablecoin, liquidity) -> str:
        """Генерирует рекомендацию на основе анализа"""
        issues = []
        
        if concentration['risk_level'] in ['CRITICAL', 'HIGH']:
            issues.append(f"Снизить концентрацию в {concentration['largest_asset']['name']}")
        
        if exchange_dep['risk_level'] in ['CRITICAL', 'HIGH']:
            issues.append(f"Распределить между биржами")
        
        if volatility['risk_level'] == 'HIGH':
            issues.append("Портфель волатилен - рассмотрите добавить стейблкоины")
        
        if liquidity['risk_level'] == 'HIGH':
            issues.append("Есть низколиквидные позиции - планируйте их выход заранее")
        
        if not issues:
            return "Портфель хорошо диверсифицирован. Продолжайте мониторить изменения."
        
        if len(issues) == 1:
            return f"Главная рекомендация: {issues[0]}"
        else:
            return f"Требуется оптимизация: {'; '.join(issues[:2])}"
