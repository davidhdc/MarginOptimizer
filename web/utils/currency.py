"""
Currency conversion utilities using live exchange rates
"""

import requests
from datetime import datetime, timedelta
import json

# Simple cache to avoid repeated API calls
_exchange_rate_cache = {}
_cache_expiry = None

def get_usd_to_brl_rate():
    """
    Get current USD to BRL exchange rate from exchangerate-api.com (free tier)

    Returns:
        float: Exchange rate (e.g., 5.40 means 1 USD = 5.40 BRL)
    """
    global _exchange_rate_cache, _cache_expiry

    # Check cache (valid for 1 hour)
    now = datetime.now()
    if _cache_expiry and now < _cache_expiry and 'USD_BRL' in _exchange_rate_cache:
        return _exchange_rate_cache['USD_BRL']

    try:
        # Using exchangerate-api.com free tier (no API key needed)
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            rate = data['rates'].get('BRL')

            if rate:
                # Cache the result for 1 hour
                _exchange_rate_cache['USD_BRL'] = rate
                _cache_expiry = now + timedelta(hours=1)
                print(f"[Currency] Fetched live USD/BRL rate: {rate}")
                return rate

    except Exception as e:
        print(f"[Currency] Error fetching exchange rate: {e}")

    # Fallback to a reasonable default if API fails
    print("[Currency] Using fallback USD/BRL rate: 5.40")
    return 5.40  # Fallback rate


def get_exchange_rate(from_currency: str, to_currency: str) -> float:
    """
    Get exchange rate between two currencies

    Args:
        from_currency: Source currency code (e.g., 'USD')
        to_currency: Target currency code (e.g., 'BRL')

    Returns:
        float: Exchange rate
    """
    # Currently only supporting USD <-> BRL
    if from_currency == 'USD' and to_currency == 'BRL':
        return get_usd_to_brl_rate()
    elif from_currency == 'BRL' and to_currency == 'USD':
        return 1.0 / get_usd_to_brl_rate()
    elif from_currency == to_currency:
        return 1.0
    else:
        # Fallback for unsupported currency pairs
        print(f"[Currency] Unsupported currency pair: {from_currency}/{to_currency}")
        return 1.0
