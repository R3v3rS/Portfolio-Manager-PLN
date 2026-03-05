from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional

import requests


class FxRateService:
    """
    Service responsible for returning FX rates to PLN.

    Supported currencies:
    - PLN (always 1.0)
    - USD
    - EUR

    Data source: NBP API (table A)
    Example endpoint: https://api.nbp.pl/api/exchangerates/rates/a/usd/
    """

    BASE_URL = "https://api.nbp.pl/api/exchangerates/rates/a"
    SUPPORTED_CURRENCIES = {"PLN", "USD", "EUR"}
    REQUEST_TIMEOUT_SECONDS = 8
    MAX_FALLBACK_DAYS = 10

    # cache key format: "USD_2026-03-01" -> 3.91
    fx_cache: Dict[str, float] = {}

    @classmethod
    def get_rate(cls, currency: str, date: Optional[str] = None) -> float:
        """
        Return FX rate for `currency` -> PLN.

        If date is provided (YYYY-MM-DD), tries historical rate for that date.
        When no quote exists for the date (weekend/holiday), it falls back to
        the most recent prior business day available from NBP.
        """
        normalized_currency = (currency or "").strip().upper()

        if normalized_currency not in cls.SUPPORTED_CURRENCIES:
            raise ValueError(
                f"Unsupported currency '{currency}'. Supported: {sorted(cls.SUPPORTED_CURRENCIES)}"
            )

        if normalized_currency == "PLN":
            return 1.0

        requested_date = cls._normalize_date(date)
        cache_key = f"{normalized_currency}_{requested_date}"

        if cache_key in cls.fx_cache:
            return cls.fx_cache[cache_key]

        rate = cls._fetch_rate_with_fallback(normalized_currency, requested_date)
        cls.fx_cache[cache_key] = rate
        return rate

    @classmethod
    def _normalize_date(cls, date_value: Optional[str]) -> str:
        if not date_value:
            return datetime.now().date().isoformat()

        try:
            parsed = datetime.strptime(date_value, "%Y-%m-%d").date()
            return parsed.isoformat()
        except ValueError as exc:
            raise ValueError("Date must be in YYYY-MM-DD format.") from exc

    @classmethod
    def _fetch_rate_with_fallback(cls, currency: str, requested_date: str) -> float:
        current_date = datetime.strptime(requested_date, "%Y-%m-%d").date()

        for _ in range(cls.MAX_FALLBACK_DAYS + 1):
            daily_cache_key = f"{currency}_{current_date.isoformat()}"
            if daily_cache_key in cls.fx_cache:
                return cls.fx_cache[daily_cache_key]

            endpoint = f"{cls.BASE_URL}/{currency.lower()}/{current_date.isoformat()}/"

            try:
                response = requests.get(
                    endpoint,
                    headers={"Accept": "application/json"},
                    timeout=cls.REQUEST_TIMEOUT_SECONDS,
                )
            except requests.RequestException as exc:
                raise RuntimeError(f"Failed to fetch FX rate from NBP API: {exc}") from exc

            if response.status_code == 200:
                rate = cls._extract_rate(response)
                cls.fx_cache[daily_cache_key] = rate
                return rate

            if response.status_code == 404:
                current_date = current_date - timedelta(days=1)
                continue

            raise RuntimeError(
                f"NBP API returned unexpected status {response.status_code} for {endpoint}"
            )

        raise RuntimeError(
            f"No FX rate found for {currency} on {requested_date} "
            f"(including {cls.MAX_FALLBACK_DAYS} fallback days)."
        )

    @staticmethod
    def _extract_rate(response: requests.Response) -> float:
        try:
            payload = response.json()
            rates = payload["rates"]
            mid = rates[0]["mid"]
            return float(mid)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("NBP API response has unexpected format.") from exc

    @classmethod
    def clear_cache(cls) -> None:
        cls.fx_cache.clear()


if __name__ == "__main__":
    # Minimal usage example
    print("USD today:", FxRateService.get_rate("USD"))
    print("EUR 2026-03-01 (fallback if needed):", FxRateService.get_rate("EUR", "2026-03-01"))
    print("PLN:", FxRateService.get_rate("PLN"))
