import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import statistics
import math

class AssetSelector:
    """
    Класс для автоматического выбора активов для торговли
    Анализирует рынок и выбирает наиболее подходящие активы
    """
    
    def __init__(self, api_client, db_manager, config_manager):
        self.api_client = api_client
        self.db = db_manager
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Параметры для анализа активов
        self.min_volume_24h = 1000000  # Минимальный объем торгов за 24ч (USDT)
        self.max_volatility = 0.15  # Максимальная волатильность (15%)
        self.min_liquidity_score = 0.6  # Минимальный балл ликвидности
        self.risk_tolerance = 0.7  # Толерантность к риску (0-1)
        
    async def select_best_assets(self, strategy_type: str = None, count: int = 5) -> List[str]:
        """
        Выбор лучших активов для торговли
        
        Args:
            strategy_type: Тип стратегии для специфичного анализа
            count: Количество активов для выбора
            
        Returns:
            Список символов лучших активов
        """
        try:
            self.logger.info(f"Начинаю анализ активов для выбора {count} лучших")
            
            # Получаем список всех доступных активов
            all_assets = await self._get_available_assets()
            if not all_assets:
                self.logger.warning("Не удалось получить список активов")
                return self._get_fallback_assets(count)
            
            # Анализируем каждый актив
            asset_scores = []
            for asset in all_assets:
                try:
                    score = await self._analyze_asset(asset, strategy_type)
                    if score > 0:
                        asset_scores.append((asset, score))
                except Exception as e:
                    self.logger.debug(f"Ошибка анализа актива {asset}: {e}")
                    continue
            
            # Сортируем по баллам и выбираем лучшие
            asset_scores.sort(key=lambda x: x[1], reverse=True)
            selected_assets = [asset for asset, score in asset_scores[:count]]
            
            if len(selected_assets) < count:
                # Дополняем fallback активами если не хватает
                fallback = self._get_fallback_assets(count - len(selected_assets))
                selected_assets.extend([a for a in fallback if a not in selected_assets])
            
            self.logger.info(f"Выбраны активы: {selected_assets}")
            return selected_assets[:count]
            
        except Exception as e:
            self.logger.error(f"Ошибка выбора активов: {e}")
            return self._get_fallback_assets(count)
    
    async def _get_available_assets(self) -> List[str]:
        """
        Получение списка доступных активов через API
        """
        try:
            if not self.api_client:
                return []
            
            # Получаем информацию о рынке
            tickers = await self.api_client.get_tickers(category="spot")
            if not tickers or 'result' not in tickers:
                return []
            
            # Фильтруем только USDT пары
            usdt_pairs = []
            for ticker in tickers['result']['list']:
                symbol = ticker.get('symbol', '')
                if symbol.endswith('USDT') and len(symbol) <= 10:
                    usdt_pairs.append(symbol)
            
            return usdt_pairs  # Возвращаем все доступные USDT пары
            
        except Exception as e:
            self.logger.error(f"Ошибка получения списка активов: {e}")
            return []
    
    async def _analyze_asset(self, symbol: str, strategy_type: str = None) -> float:
        """
        Анализ конкретного актива и расчет его балла
        
        Args:
            symbol: Символ актива
            strategy_type: Тип стратегии для специфичного анализа
            
        Returns:
            Балл актива (0-100)
        """
        try:
            # Получаем данные о тикере
            ticker_data = await self._get_ticker_data(symbol)
            if not ticker_data:
                return 0
            
            # Получаем исторические данные
            klines = await self._get_kline_data(symbol)
            if not klines:
                return 0
            
            # Рассчитываем различные метрики
            volume_score = self._calculate_volume_score(ticker_data)
            volatility_score = self._calculate_volatility_score(klines)
            liquidity_score = self._calculate_liquidity_score(ticker_data)
            trend_score = self._calculate_trend_score(klines)
            risk_score = self._calculate_risk_score(klines, ticker_data)
            
            # Специфичные баллы для типа стратегии
            strategy_score = self._calculate_strategy_specific_score(klines, ticker_data, strategy_type)
            
            # Итоговый балл с весами
            total_score = (
                volume_score * 0.2 +
                volatility_score * 0.15 +
                liquidity_score * 0.2 +
                trend_score * 0.15 +
                risk_score * 0.15 +
                strategy_score * 0.15
            )
            
            return min(100, max(0, total_score))
            
        except Exception as e:
            self.logger.debug(f"Ошибка анализа актива {symbol}: {e}")
            return 0
    
    async def _get_ticker_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение данных тикера
        """
        try:
            if not self.api_client:
                return None
                
            response = await self.api_client.get_tickers(category="spot", symbol=symbol)
            if response and 'result' in response and 'list' in response['result']:
                return response['result']['list'][0] if response['result']['list'] else None
            return None
            
        except Exception as e:
            self.logger.debug(f"Ошибка получения данных тикера {symbol}: {e}")
            return None
    
    async def _get_kline_data(self, symbol: str, interval: str = "1h", limit: int = 168) -> Optional[List]:
        """
        Получение исторических данных (klines)
        """
        try:
            if not self.api_client:
                return None
                
            response = await self.api_client.get_kline(
                category="spot",
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            if response and 'result' in response and 'list' in response['result']:
                return response['result']['list']
            return None
            
        except Exception as e:
            self.logger.debug(f"Ошибка получения kline данных {symbol}: {e}")
            return None
    
    def _calculate_volume_score(self, ticker_data: Dict) -> float:
        """
        Расчет балла объема торгов
        """
        try:
            volume_24h = float(ticker_data.get('turnover24h', 0))
            
            if volume_24h < self.min_volume_24h:
                return 0
            
            # Логарифмическая шкала для объема
            score = min(100, (math.log10(volume_24h) - math.log10(self.min_volume_24h)) * 20)
            return max(0, score)
            
        except (ValueError, TypeError):
            return 0
    
    def _calculate_volatility_score(self, klines: List) -> float:
        """
        Расчет балла волатильности
        """
        try:
            if len(klines) < 24:
                return 0
            
            # Рассчитываем волатильность за последние 24 часа
            prices = [float(kline[4]) for kline in klines[:24]]  # Цены закрытия
            
            if len(prices) < 2:
                return 0
            
            # Стандартное отклонение цен
            mean_price = statistics.mean(prices)
            volatility = statistics.stdev(prices) / mean_price
            
            # Оптимальная волатильность 2-8%
            if 0.02 <= volatility <= 0.08:
                return 100
            elif volatility < 0.02:
                return volatility * 5000  # Слишком низкая
            elif volatility > self.max_volatility:
                return 0  # Слишком высокая
            else:
                return max(0, 100 - (volatility - 0.08) * 1000)
            
        except (ValueError, TypeError, statistics.StatisticsError):
            return 0
    
    def _calculate_liquidity_score(self, ticker_data: Dict) -> float:
        """
        Расчет балла ликвидности
        """
        try:
            # Используем спред между bid и ask как показатель ликвидности
            bid = float(ticker_data.get('bid1Price', 0))
            ask = float(ticker_data.get('ask1Price', 0))
            
            if bid <= 0 or ask <= 0:
                return 50  # Средний балл если данных нет
            
            spread = (ask - bid) / ((ask + bid) / 2)
            
            # Чем меньше спред, тем лучше ликвидность
            if spread <= 0.001:  # 0.1%
                return 100
            elif spread <= 0.005:  # 0.5%
                return 80
            elif spread <= 0.01:  # 1%
                return 60
            else:
                return max(0, 60 - (spread - 0.01) * 1000)
            
        except (ValueError, TypeError):
            return 50
    
    def _calculate_trend_score(self, klines: List) -> float:
        """
        Расчет балла тренда
        """
        try:
            if len(klines) < 48:
                return 50
            
            # Анализируем тренд за последние 48 часов
            prices = [float(kline[4]) for kline in klines[:48]]
            
            # Простая линейная регрессия для определения тренда
            n = len(prices)
            x_values = list(range(n))
            
            sum_x = sum(x_values)
            sum_y = sum(prices)
            sum_xy = sum(x * y for x, y in zip(x_values, prices))
            sum_x2 = sum(x * x for x in x_values)
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            
            # Нормализуем наклон относительно средней цены
            avg_price = sum_y / n
            normalized_slope = slope / avg_price
            
            # Слабый восходящий тренд предпочтителен
            if 0.001 <= normalized_slope <= 0.01:
                return 100
            elif -0.001 <= normalized_slope <= 0.001:
                return 70  # Боковой тренд
            else:
                return max(0, 70 - abs(normalized_slope) * 1000)
            
        except (ValueError, TypeError, ZeroDivisionError):
            return 50
    
    def _calculate_risk_score(self, klines: List, ticker_data: Dict) -> float:
        """
        Расчет балла риска
        """
        try:
            if len(klines) < 24:
                return 50
            
            # Анализируем максимальные просадки
            prices = [float(kline[4]) for kline in klines[:24]]
            
            max_drawdown = 0
            peak = prices[0]
            
            for price in prices:
                if price > peak:
                    peak = price
                drawdown = (peak - price) / peak
                max_drawdown = max(max_drawdown, drawdown)
            
            # Чем меньше просадка, тем лучше
            if max_drawdown <= 0.05:  # 5%
                return 100
            elif max_drawdown <= 0.1:  # 10%
                return 80
            elif max_drawdown <= 0.2:  # 20%
                return 60
            else:
                return max(0, 60 - (max_drawdown - 0.2) * 200)
            
        except (ValueError, TypeError):
            return 50
    
    def _calculate_strategy_specific_score(self, klines: List, ticker_data: Dict, strategy_type: str) -> float:
        """
        Расчет балла специфичного для стратегии
        """
        try:
            if not strategy_type or len(klines) < 24:
                return 50
            
            if "momentum" in strategy_type.lower():
                return self._momentum_strategy_score(klines)
            elif "grid" in strategy_type.lower():
                return self._grid_strategy_score(klines)
            elif "ma" in strategy_type.lower() or "средние" in strategy_type.lower():
                return self._ma_strategy_score(klines)
            else:
                return 50
            
        except Exception:
            return 50
    
    def _momentum_strategy_score(self, klines: List) -> float:
        """
        Балл для momentum стратегии
        """
        try:
            prices = [float(kline[4]) for kline in klines[:24]]
            
            # Ищем четкие импульсы
            momentum_changes = []
            for i in range(1, len(prices)):
                change = (prices[i] - prices[i-1]) / prices[i-1]
                momentum_changes.append(abs(change))
            
            avg_momentum = statistics.mean(momentum_changes)
            
            # Оптимальный momentum 0.5-2%
            if 0.005 <= avg_momentum <= 0.02:
                return 100
            else:
                return max(0, 100 - abs(avg_momentum - 0.0125) * 4000)
            
        except Exception:
            return 50
    
    def _grid_strategy_score(self, klines: List) -> float:
        """
        Балл для grid стратегии
        """
        try:
            prices = [float(kline[4]) for kline in klines[:48]]
            
            # Ищем боковое движение
            price_range = max(prices) - min(prices)
            avg_price = statistics.mean(prices)
            range_pct = price_range / avg_price
            
            # Оптимальный диапазон 3-8%
            if 0.03 <= range_pct <= 0.08:
                return 100
            else:
                return max(0, 100 - abs(range_pct - 0.055) * 1000)
            
        except Exception:
            return 50
    
    def _ma_strategy_score(self, klines: List) -> float:
        """
        Балл для стратегии скользящих средних
        """
        try:
            prices = [float(kline[4]) for kline in klines[:50]]
            
            if len(prices) < 20:
                return 50
            
            # Рассчитываем MA20
            ma20 = statistics.mean(prices[:20])
            current_price = prices[0]
            
            # Проверяем четкость тренда относительно MA
            distance_from_ma = abs(current_price - ma20) / ma20
            
            # Оптимальное расстояние 1-5%
            if 0.01 <= distance_from_ma <= 0.05:
                return 100
            else:
                return max(0, 100 - abs(distance_from_ma - 0.03) * 2000)
            
        except Exception:
            return 50
    
    def _get_fallback_assets(self, count: int) -> List[str]:
        """
        Получение резервного списка активов
        """
        fallback_assets = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
            "ADAUSDT", "DOGEUSDT", "MATICUSDT", "DOTUSDT", "AVAXUSDT",
            "LINKUSDT", "UNIUSDT", "LTCUSDT", "ATOMUSDT", "NEARUSDT"
        ]
        return fallback_assets[:count]
    
    def get_asset_analysis_summary(self, symbol: str) -> Dict[str, Any]:
        """
        Получение сводки анализа актива
        """
        try:
            # Здесь можно добавить детальный анализ для отображения пользователю
            return {
                "symbol": symbol,
                "recommendation": "Подходит для торговли",
                "risk_level": "Средний",
                "liquidity": "Высокая",
                "volatility": "Умеренная"
            }
        except Exception as e:
            self.logger.error(f"Ошибка получения сводки анализа {symbol}: {e}")
            return {}