# Changelog Dokumentacji

**Data:** 2026-04-02

## Zmienione pliki
- `docs/AUDIT_AND_IMPROVEMENT_PLAN.md`
- `docs/PROJECT_GUIDE.md`
- `docs/DOCUMENTATION_CHANGELOG.md` (nowy)

---

## Co zostało zmienione

1. Zastąpiono treść audytową w stylu roadmapy ustrukturyzowanym dokumentem audytu technicznego.
2. Przepisano project guide do formy deterministycznej specyfikacji source-of-truth.
3. Dodano jawne reguły i wzory dla:
   - własności transakcji (`portfolio_id` parent, `sub_portfolio_id` child scope),
   - SELL cost basis (`total_cost -= sold_qty * avg_price`),
   - agregacji średniej ważonej parenta (`SUM(total_cost) / SUM(quantity)`),
   - parsowania ilości ułamkowej XTB (`"1/5" -> 1`),
   - normalizacji przepływu gotówki (`tx_total = abs(amount)`).
4. Dodano jawne rozdzielenie: ledger transakcji (source-of-truth) vs holdings (stan pochodny).
5. Dodano edge-case’y i rejestr ryzyk (precyzja, FX, agregacja, rounding).
6. Ujednolicono terminologię między dokumentami.

---

## Dlaczego to zostało zmienione

1. Poprzednia dokumentacja mieszała onboarding/status/architekturę bez deterministycznych reguł księgowych.
2. Krytyczne zachowania backendu istniały w implementacji, ale nie były zapisane jako kontrakt dokumentacyjny.
3. Niespójna terminologia zwiększała ryzyko błędnej interpretacji przy dalszym rozwoju.
4. Brak jawnych wzorów SELL i agregacji groził błędnymi implementacjami w przyszłości.

---

## Kluczowe usprawnienia

1. Dokumentacja zawiera teraz jawne, testowalne inwarianty księgowe.
2. Semantyka zakresów parent/child jest jednoznaczna.
3. Zachowanie importu XTB (ilość i normalizacja kwot) jest jawnie opisane.
4. Rejestr ryzyk jest powiązany z potencjalnymi błędami poprawności.
5. Project guide jest dokumentem referencyjnym implementacji, a nie tylko onboardingiem.

---

## Wykryte ryzyka do monitorowania

1. Mieszana precyzja float + decimal między runtime i audytem.
2. Możliwe rozjazdy interpretacji FX między wyceną a założeniami book-cost.
3. Rozproszona logika agregacji w wielu serwisach (powierzchnia regresji).
4. Dryf zaokrągleń przy powtarzalnych partial sell.
5. Narzut wydajnościowy rekonstrukcji historii dla dużych ledgerów.

