from typing import Dict, Any

def get_historical_data(api_client, symbol: str, interval: str = '1h', limit: int = 100) -> Dict[str, Any]:
    """
    Получение исторических данных для анализа
    
    Args:
        api_client: API клиент для Bybit
        symbol: Торговый символ
        interval: Интервал свечей (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w, 1M)
        limit: Количество свечей для получения (максимум 1000)
        
    Returns:
        Исторические данные в формате словаря
    """
    try:
        # Проверка валидности интервала
        valid_intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w', '1M']
        if interval not in valid_intervals:
            return {
                'status': 'error',
                'message': f'Неверный интервал. Допустимые значения: {valid_intervals}'
            }
            
        # Проверка лимита
        if limit <= 0 or limit > 1000:
            return {
                'status': 'error',
                'message': 'Количество свечей должно быть от 1 до 1000'
            }
            
        # Получение исторических данных через API
        kline_params = {
            'category': 'linear',
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        kline_result = api_client.get_kline(**kline_params)
        
        # Проверка результата
        if not kline_result or 'result' not in kline_result or 'list' not in kline_result['result']:
            return {
                'status': 'error',
                'message': 'Не удалось получить исторические данные',
                'raw_result': kline_result
            }
            
        # Преобразование данных в удобный формат
        candles = kline_result['result']['list']
        formatted_candles = []
        
        for candle in candles:
            # Bybit возвращает данные в формате [timestamp, open, high, low, close, volume, ...]
            formatted_candles.append({
                'timestamp': int(candle[0]),
                'open': float(candle[1]),
                'high': float(candle[2]),
                'low': float(candle[3]),
                'close': float(candle[4]),
                'volume': float(candle[5])
            })
            
        return {
            'status': 'success',
            'interval': interval,
            'symbol': symbol,
            'candles': formatted_candles,
            'count': len(formatted_candles)
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Ошибка при получении исторических данных: {e}',
            'error': str(e)
        }