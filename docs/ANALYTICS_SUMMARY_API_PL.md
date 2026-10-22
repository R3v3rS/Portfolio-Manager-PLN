# Podsumowanie analiz — `/api/analytics/summary`

Stan: 22 października 2026. [Zakres API](API_ZAKRES_PL.md) · [Architektura](ARCHITEKTURA_I_MODEL_DANYCH_PL.md).

## Parametry i zakres

`GET /api/analytics/summary` przyjmuje:

| Parametr | Znaczenie |
|---|---|
| `portfolio_id` | Wymagany identyfikator portfela, liczba całkowita > 0 |
| `sub_portfolio_id` | Opcjonalny identyfikator strategii należącej do tego portfela |
| `period` | `3mo`, `6mo`, `1y`, `2y`; aliasy `3m` i `6m` są normalizowane do `3mo` i `6mo`. Domyślnie `1y` |

Resolver ustala właściciela i zakres strategii; identyfikator dziecka może zostać znormalizowany do rodzica i `sub_portfolio_id`. Brak filtra strategii oznacza zakres portfela głównego, nie wyłącznie jego część własną.

Analiza opisuje model **obecnego koszyka akcyjnego** i wspólną historię notowań, bez gotówki i pełnego odtworzenia historycznych zmian składu. Nie jest rzeczywistą stopą zwrotu konta ani analizą PPK, obligacji i oszczędności. Faktyczny zakres mogą ograniczać krótsze szeregi cenowe. Sprawdzaj `data_status`, `data_points`, `observed_from`, `observed_to` oraz `requested_from` we właściwych sekcjach.

## Odpowiedź i jednostki

Odpowiedź ma kopertę `payload`, identyfikatory znormalizowanego zakresu, `period`, `cached` oraz sekcje:

- `performance`: Sharpe, maksymalne obsunięcie, zmienność, zwrot i przebieg obsunięć;
- `risk`: historyczny VaR i CVaR 1D dla poziomu ufności 95%;
- `correlation`: korelacje i dane do wizualizacji;
- `diversification`: rozproszenie instrumentów i sektorów. HHI nie opisuje spółek wewnątrz ETF.

| Pole | Interpretacja |
|---|---|
| `performance.sharpe_ratio` | Roczna miara obliczana z dziennych logarytmicznych stóp; domyślne `risk_free_rate=0.05` |
| `performance.max_drawdown` | Obiekt: `value`, `start_date`, `end_date`, `recovery_date`, `duration_days`; wartość −0,12 oznacza −12% |
| `performance.volatility_annualized` | Ułamek: 0,20 oznacza 20% |
| `performance.total_return_pct` | Procenty: 12 oznacza 12% |
| `performance.drawdown_series[].value` | Procenty: −12 oznacza −12% |
| `risk.var_1d_pct`, `risk.var_1d_percent` | Ta sama stopa kwantyla ogona jako ułamek, np. −0,018; interfejs pokazuje wartość bezwzględną |
| `risk.var_1d_pln` | Kwota w PLN ze znakiem wynikającym z kwantyla; nie pole `var_1d` z dawnego przykładu |
| `risk.cvar_1d_pct`, `risk.cvar_1d_pln` | Średnia dla ogona rozkładu, odpowiednio stopa i kwota |

Przy niedostatecznych danych wynik może być `null`. Nie zamieniaj go na zero. Statusy obejmują `ok`, `no_holdings`, `insufficient_history`, `missing_prices`. VaR nie jest gwarantowaną granicą strat.

Backend zwraca także aliasy zgodności: `performance_summary`, `portfolio_var`, `correlation_risk`. Nie dodawaj ich do nowych sekcji jako kolejnych wyników. Fragment przykładowego `payload` (bez pozostałych sekcji i pól):

```json
{
  "portfolio_id": 1,
  "sub_portfolio_id": null,
  "period": "1y",
  "cached": false,
  "performance": {
    "sharpe_ratio": 1.24,
    "max_drawdown": {
      "value": -0.12,
      "start_date": "2026-01-05",
      "end_date": "2026-02-10",
      "recovery_date": null,
      "duration_days": 36
    }
  },
  "risk": {"var_1d_pct": -0.018, "var_1d_percent": -0.018, "var_1d_pln": -1500.0}
}
```

## Pamięć podręczna i błędy

`analytics_cache` jest inicjalizowana podczas rejestracji blueprintu. Klucz obejmuje portfel, strategię i okres. TTL wynosi 4 godziny, ale odczyt dodatkowo porównuje wersję schematu i sygnaturę pozycji oraz cen/FX z `price_cache`. Zmiana tego stanu unieważnia wynik przed upływem TTL. Samo `cached=false` nie oznacza, że wszystkie ceny są z dzisiaj.

Przy braku poprawnego cache backend równolegle uruchamia serwisy wyników, VaR, korelacji i rozproszenia, normalizuje wynik oraz zapisuje go w cache. Błędne parametry zwracają błąd walidacji, nieistniejący portfel 404, a nieoczekiwany błąd obliczeń `analytics_summary_error` z HTTP 500.

```bash
curl "http://127.0.0.1:5000/api/analytics/summary?portfolio_id=1&period=1y"
curl "http://127.0.0.1:5000/api/analytics/summary?portfolio_id=1&sub_portfolio_id=2&period=6mo"
```

Implementacja: `backend/routes_analytics.py` i `backend/services/analytics/`. Klient: `frontend/src/api_analytics.ts`; widok: `frontend/src/components/analytics/AnalyticsDashboard.tsx`.
