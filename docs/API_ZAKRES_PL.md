# Zakres dokumentacji API

Stan: 22 października 2026. [Spis dokumentacji](README.md) · [Architektura](ARCHITEKTURA_I_MODEL_DANYCH_PL.md).

## Trzy różne źródła informacji

- `backend/app.py` i zarejestrowane blueprinty określają dostępne trasy. Klienci `frontend/src/api*.ts` pokazują sposób ich używania przez interfejs.
- [Test kontraktu](../backend/tests/test_api_contract.py) sprawdza obsługę zarejestrowanych tras i kopertę odpowiedzi. Nie zastępuje specyfikacji pól ani testów domenowych.
- [OpenAPI](openapi.yaml) opisuje wybrany fragment API. Brak ścieżki w tym pliku nie oznacza braku funkcji w aplikacji.

## Co obejmuje OpenAPI

Serwer bazowy to `/api`; podane poniżej ścieżki są względne wobec niego. Schematy części starszych odpowiedzi dopuszczają dodatkowe pola, dlatego nie jest to pełny model typów frontendu.

| Metoda i ścieżka | Zakres |
|---|---|
| `POST /portfolio/{portfolio_id}/import/xtb` | Bezpośredni import, nie cały proces sesji podglądu; oryginalny XLSX Cash Operations i CSV |
| `GET`, `POST /symbol-map` oraz `PUT`, `DELETE /symbol-map/{mapping_id}` | Mapowanie symboli |
| `GET`, `POST /loans/` i `GET /loans/{loan_id}/schedule` | Wybrane operacje kredytów, bez pełnego rozliczania płatności |
| `GET /analytics/summary` | Parametry i koperta zbiorczych analiz; szczegóły w [referencji podsumowania](ANALYTICS_SUMMARY_API_PL.md) |
| `GET /ai/settings` i `GET /ai/context/{pid}` | Odczyt konfiguracji i kontekstu; bez generowania AI |

## Gdzie szukać pozostałych operacji

Budżet, rachunki, rezerwy, prognozę, import bankowy i zamknięcie opisują [architektura](ARCHITEKTURA_I_MODEL_DANYCH_PL.md#8-najważniejsze-grupy-api) oraz odpowiadające im `routes_budget*.py`, `routes_cash_forecast.py` i klienci frontendu. [Referencja analiz](AI_PORTFOLIO_ANALYSIS_MODULE_PL.md#dane-api-i-testy) opisuje rozmowy, plan udziałów, skład ETF i materiały.

Kolejne uzupełnienia powinny obejmować najpierw operacje zmieniające salda i powiązania: płatności, cofnięcia, importy i przelewy. Dla każdej należy opisać wersję/podgląd, identyfikator ponowienia, błędy i skutki zapisu. Nie należy dopisywać ogólnego schematu „dowolny obiekt” jako pozornie kompletnego kontraktu wszystkich operacji.
