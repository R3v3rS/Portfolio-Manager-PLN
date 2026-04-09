# Dokumentacja funkcji Analytics Summary (`/api/analytics/summary`)

## Cel funkcji
Endpoint dostarcza zagregowane metryki analityczne portfela do zakładki **Analytics Dashboard**. Łączy dane z kilku serwisów analitycznych i zwraca jeden spójny kontrakt dla frontendu.

## Endpoint
- **Metoda:** `GET`
- **Ścieżka:** `/api/analytics/summary`

## Parametry zapytania
- `portfolio_id` *(wymagany, int > 0)*
- `sub_portfolio_id` *(opcjonalny, int > 0)*
- `period` *(opcjonalny)*: `3m`, `6m`, `1y`, `2y` (domyślnie `1y`)

## Walidacja
- Brak `portfolio_id` → błąd walidacji.
- Niepoprawny format `portfolio_id`/`sub_portfolio_id` → błąd walidacji.
- Wartość `<= 0` → błąd walidacji.
- Nieobsługiwany `period` → błąd walidacji z listą wspieranych okresów.
- Nieistniejący portfel → `Portfolio not found`.

## Cache
- Wyniki są buforowane w tabeli SQLite: `analytics_cache`.
- Klucz cache: `(portfolio_id, sub_portfolio_id, period)`.
- TTL cache: **4 godziny**.
- Pole `cached` w odpowiedzi:
  - `true` → dane z cache,
  - `false` → świeżo przeliczone.

## Jak liczone są dane
Dla braku cache backend równolegle uruchamia:
1. `calculate_performance_summary(...)`
2. `portfolio_var(...)`
3. `portfolio_correlation_risk(...)`
4. `diversification_score(...)`

Następnie wynik jest normalizowany do jednego kontraktu i zapisywany do cache.

## Kontrakt odpowiedzi (payload)
```json
{
  "portfolio_id": 1,
  "sub_portfolio_id": 2,
  "period": "1y",
  "cached": false,
  "performance": {
    "sharpe_ratio": 1.24,
    "max_drawdown": -0.12
  },
  "risk": {
    "var_1d": 1500.0,
    "var_1d_percent": 0.018
  },
  "correlation": {
    "recharts_data": []
  },
  "diversification": {
    "score": 62.5,
    "by_sector": []
  },
  "performance_summary": {
    "sharpe_ratio": 1.24,
    "max_drawdown": -0.12
  },
  "portfolio_var": {
    "var_1d": 1500.0,
    "var_1d_percent": 0.018
  },
  "correlation_risk": {
    "recharts_data": []
  }
}
```

## Zgodność wsteczna
Backend zwraca jednocześnie nowe i legacy nazwy pól:
- nowe: `performance`, `risk`, `correlation`, `diversification`
- legacy: `performance_summary`, `portfolio_var`, `correlation_risk`

Frontend normalizuje obie wersje kontraktu (m.in. mapowanie `var_1d_pct` → `var_1d_percent`).

## Przykłady użycia
### Tylko portfel główny
```bash
curl "http://localhost:5000/api/analytics/summary?portfolio_id=1&period=1y"
```

### Z subportfelem
```bash
curl "http://localhost:5000/api/analytics/summary?portfolio_id=1&sub_portfolio_id=2&period=6m"
```

## Integracja z UI
Dane są konsumowane przez:
- `frontend/src/api_analytics.ts` (normalizacja payloadu),
- `frontend/src/components/analytics/AnalyticsDashboard.tsx` (widok kart metryk + heatmapa + wykres dywersyfikacji).

## Uwagi implementacyjne
- Tabela `analytics_cache` jest tworzona automatycznie podczas rejestracji blueprintu.
- W przypadku nieoczekiwanego wyjątku endpoint zwraca błąd `analytics_summary_error` (HTTP 500).
