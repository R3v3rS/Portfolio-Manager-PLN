# Kontrola jakości i mapa testów

Stan: 23 października 2026. [Spis dokumentacji](README.md). To mapa obszarów i wybranych scenariuszy, nie pełna lista testów ani deklaracja kompletnego pokrycia. Aktualne nazwy przypadków i wyniki wynikają z kodu oraz konkretnego przebiegu.

## Uruchamianie

Przygotuj zależności według [instrukcji uruchamiania](URUCHAMIANIE_I_KOPIE_PL.md). W środowisku Pythona backendu, z katalogu głównego repozytorium:

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend/tests --collect-only -q
python -m pytest backend/tests -q
```

`--collect-only` zbiera przypadki bez wykonywania ich treści; importy modułów nadal są wykonywane. Testy domenowe używają odrębnych baz, ale część starszych testów tworzy aplikację przed przełączeniem konfiguracji. Przed pełnym przebiegiem zachowaj kopię lokalnej bazy. Nie uruchamiaj testów na jedynej kopii danych użytkownika. Nie wyłączaj globalnie funkcji, którą bada test, np. automatycznych kopii podczas testowania kopii.

W katalogu `frontend/`:

```bash
npm ci
npm run check
npm run lint
npm test
npm run build
```

Na środowisku z Bash dostępny jest `scripts/run_quality_gate.sh`, opcjonalnie z `PYTHON_BIN`. Sukces lokalny i wynik GitHub Actions to osobne wyniki; brak uruchomienia z powodu konfiguracji lub rozliczeń platformy nie jest wykonanym testem.

## Budżet

| Obszar | Ważne scenariusze | Wybrane testy backendu |
|---|---|---|
| Konta i historia | Saldo początkowe poza dochodem, korekta, przelew, zakup już uwzględniony w saldzie | [konta](../backend/tests/test_budget_accounts.py), [wpływ na saldo](../backend/tests/test_budget_entry_balance.py) |
| Plan kategorii | Podkategorie bez podwójnego planu, wyjątek 0 zł, wersje domyślne, przesunięcie limitu | [podkategorie](../backend/tests/test_budget_subcategories.py), [plan domyślny](../backend/tests/test_budget_default_plans.py), [obsługa planu](../backend/tests/test_budget_usability.py) |
| Rachunki i raty | Powiązanie importu, jedno obciążenie, konto kredytu, cofnięcie | [regresje](../backend/tests/test_budget_audit_regressions.py), [kredyty](../backend/tests/test_loans_workspace.py) |
| Dochody i podsumowania | Dochód planowany i otrzymany, wolna kwota miesiąca, wydatki | [dochody](../backend/tests/test_budget_planned_income.py), [przychody miesiąca](../backend/tests/test_budget_month_income.py), [wydatki](../backend/tests/test_budget_spending_summary.py) |
| Rezerwy i media | Początek odkładania, brak drugiego kosztu, podgląd i rollback, nadwyżka, cofnięcie, zbiorczy zapis | [media](../backend/tests/test_budget_media.py), [start rezerwy](../backend/tests/test_budget_reserve_start.py), [operacje rezerw](../backend/tests/test_budget_reserve_operations.py) |
| Karty kredytowe | Miesiąc zakupu, spłata bez drugiego wydatku, zwrot, dług i majątek | [karty](../backend/tests/test_budget_credit_cards.py) |
| Import i zamknięcie | Reguły, duplikaty, jawny wpływ na saldo, trwałość decyzji | [importy](../backend/tests/test_budget_imports.py), [planowanie](../backend/tests/test_budget_planning.py) |
| Tempo i prognoza | Wyłączenia kategorii, płatności stałe poza tempem, zakresy i źródła planu | [tempo](../backend/tests/test_budget_chart_pace.py), [bezpieczeństwo](../backend/tests/test_budget_safety.py) |

Interakcje sprawdzają m.in. [BudgetUsability](../frontend/src/components/budget/BudgetUsability.test.tsx), [ReserveOperations](../frontend/src/components/budget/ReserveOperations.test.tsx), [BudgetImports](../frontend/src/pages/BudgetImports.test.tsx), [BudgetAccounts](../frontend/src/pages/BudgetAccounts.test.tsx) i [CashForecast](../frontend/src/pages/CashForecast.test.tsx). Zmiana wspólnych obliczeń wymaga sprawdzenia powiązanych obszarów, nie tylko jednego ekranu.

Czytelność budżetu i tryby pracy sprawdzają dodatkowo:

- [BudgetModes](../frontend/src/components/budget/BudgetModes.test.tsx): dostępność operacji w przeglądaniu i zarządzaniu oraz ochrona niezapisanych zmian.
- [BudgetSummary](../frontend/src/components/budget/BudgetSummary.test.tsx): bilans dochodów miesiąca, bieżące pieniądze i prognoza z jawnymi brakami danych.
- [BudgetSpendingBreakdown](../frontend/src/components/budget/BudgetSpendingBreakdown.test.tsx): wykorzystanie planu, udział w wydatkach, przekroczenia i zwroty.
- [BudgetReadability](../frontend/src/components/budget/BudgetReadability.test.tsx): wspólne płatności rachunków i kredytów, brak powtórzonych przypomnień, rozwijanie listy oraz rozdzielenie miesięcznego odłożenia od całego celu.

Testy interakcji nie zastępują oceny wyglądu. Po zmianie układu sprawdź na komputerze i telefonie przewijanie, długość nazw, kwoty, rozwijane szczegóły oraz edycję jednej pozycji bez zapisywania próbnych danych finansowych.

## Inwestycje i integracje

| Obszar | Wybrane testy |
|---|---|
| Wyniki, ceny i FX, zakresy portfeli | [wyniki](../backend/tests/test_actual_results.py), [korekty inwestycji](../backend/tests/test_investment_corrections.py), [wycena](../backend/tests/test_portfolio_valuation_service.py) |
| Import, atomowość, identyfikatory XTB, sesje | [XLSX](../backend/tests/test_xtb_xlsx_import.py), [sesje importu](../backend/tests/test_import_staging_service.py), [trasy importu](../backend/tests/test_routes_imports.py) |
| PPK i obligacje | [PPK](../backend/tests/test_ppk_service.py), [obligacje](../backend/tests/test_bonds_workspace.py) |
| AI, stan rozmowy, dziennik, limit i ponowienia, dopłata, częściowy skład ETF, potwierdzenie materiału | [backend](../backend/tests/test_investment_analysis.py), [interfejs](../frontend/src/components/ai/InvestmentAnalysis.test.tsx) |
| Publikacje i źródła | [pomysły](../backend/tests/test_investment_ideas.py), [materiały](../frontend/src/pages/InvestmentIdeas.test.tsx) |
| Kopie, retencja i odzyskiwanie po błędzie migracji | [kopie](../backend/tests/test_backups.py) |
| Koperta odpowiedzi zarejestrowanych tras | [kontrakt API](../backend/tests/test_api_contract.py) |

Testy AI zastępują dostawcę atrapą. Nie potwierdzają dostępności modelu, taryfy ani jakości rzeczywistej odpowiedzi. Test koperty API nie dowodzi zgodności wszystkich pól z częściowym `openapi.yaml`.

## Dalsza weryfikacja

Po zmianach integracji sprawdź dostępność źródła i komunikaty błędów; nie uruchamiaj automatycznie płatnych analiz w zwykłym zestawie testów. Dla dużych historii osobno oceniaj wydajność i pamięć. [Benchmark historii i wyceny](../backend/benchmarks/bench_history_valuation.py) jest pomiarem pomocniczym, nie gwarancją czasu odpowiedzi na dowolnych danych.

Rozszerzając [częściowy opis OpenAPI](openapi.yaml), sprawdzaj metodę, ścieżkę, parametry, kopertę, pola opcjonalne i błędy z trasą oraz klientem frontendu. Uzupełniaj scenariusze regresyjne dla wykrytego problemu. Dawne listy „brakujących testów” nie zastępują przeglądu aktualnego pokrycia.
