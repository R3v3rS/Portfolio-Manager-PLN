# Portfolio Manager (PLN)

Portfolio Manager (PLN) to aplikacja do zarządzania finansami osobistymi, portfelami inwestycyjnymi, budżetem domowym, kredytami oraz analizą majątku netto.

Repozytorium jest utrzymywane jako monolit z dwoma głównymi częściami:

- `backend/` — API w Flasku oparte o SQLite,
- `frontend/` — interfejs React + TypeScript budowany przez Vite.

## Co potrafi aplikacja

### Inwestycje
- wiele portfeli inwestycyjnych,
- wpłaty, wypłaty, kupno i sprzedaż aktywów,
- obsługa akcji, ETF-ów, obligacji, kont oszczędnościowych i PPK,
- historia wartości, wyników i pozycji,
- import CSV z XTB,
- mapowanie symboli brokerowych,
- watchlista i radar inwestycyjny.

### Budżet domowy
- konta budżetowe i historia transakcji,
- koperty, kategorie i alokowanie środków,
- analityka miesięczna,
- transfery budżet ↔ inwestycje,
- pożyczki między kopertami.

### Kredyty i majątek netto
- lista kredytów i harmonogramy spłat,
- nadpłaty oraz zmiany oprocentowania,
- symulacje skrócenia okresu lub obniżenia rat,
- globalny dashboard majątku netto łączący budżet, inwestycje i zobowiązania.

## Architektura w skrócie

1. React renderuje widoki zdefiniowane w `frontend/src/App.tsx`.
2. Strony i komponenty korzystają z warstwy API w `frontend/src/api*.ts`, a requesty HTTP przechodzą przez wspólny klient z `frontend/src/http.ts`.
3. Flask rejestruje blueprinty pod `/api/portfolio`, `/api/budget`, `/api/loans`, `/api/dashboard`, `/api/radar` i `/api/symbol-map`.
4. Routy delegują logikę do serwisów domenowych.
5. Serwisy zapisują dane bezpośrednio do SQLite przez `database.py`.
6. Część danych rynkowych jest pobierana z zewnętrznych źródeł i cache’owana lokalnie.


## Zasada architektoniczna frontendu

- komponenty i strony **nie wykonują bezpośrednich requestów HTTP**; korzystają wyłącznie z warstwy API (`frontend/src/api*.ts`),
- helpery infrastrukturalne używają wspólnego klienta HTTP z `frontend/src/http.ts`,
- endpointy backendowe powinny być budowane przez wspólną konfigurację API, bez rozproszonych, twardo kodowanych baz URL.

## Najważniejsze katalogi

```text
.
├── backend/
│   ├── app.py
│   ├── database.py
│   ├── routes*.py
│   ├── *_service.py
│   └── modules/ppk/
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   ├── components/
│   │   ├── api*.ts
│   │   ├── services/
│   │   └── types.ts
│   └── package.json
├── docs/
│   └── PROJECT_GUIDE.md
└── README.md
```

## Wymagania

- Python 3.11+
- Node.js 18+
- npm 9+

## Uruchomienie lokalne

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

API domyślnie działa pod `http://127.0.0.1:5000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend domyślnie działa pod `http://localhost:5173`.

## Najważniejsze komendy developerskie

### Frontend

```bash
cd frontend
npm run dev
npm run check
npm run build
npm run lint
```

### Backend

```bash
cd backend
python app.py
python -m compileall .
```

## Dokumentacja projektu

Aktualna dokumentacja repo jest rozbita na dwa poziomy:

- `README.md` — szybki opis produktu, stosu i uruchomienia,
- `docs/PROJECT_GUIDE.md` — pełny przewodnik po architekturze, modułach, zależnościach, danych, przepływach requestów i onboarding dla developera lub AI,
- `docs/IMPROVEMENT_PLAN.md` — plan usprawnień aplikacji z priorytetami, etapami wdrożenia i listą quick wins.

Jeśli zaczynasz pracę w projekcie, najlepsza kolejność to:

1. przeczytać ten plik,
2. otworzyć `backend/app.py`, `backend/database.py` i `frontend/src/App.tsx`,
3. przejść przez `docs/PROJECT_GUIDE.md`,
4. wybrać jeden moduł domenowy i prześledzić go end-to-end.

## Porządek dokumentacji

W repo zostały usunięte stare lub mylące dokumenty pomocnicze, które dublowały informacje albo opisywały nieaktualny stan projektu. Od teraz punktem wejścia są wyłącznie ten `README.md` oraz `docs/PROJECT_GUIDE.md`.


## Quality gate

Minimalny quality gate dla formalnego domknięcia Etapu 1 uruchomisz jednym poleceniem:

```bash
./scripts/run_quality_gate.sh
```

Skrypt wykonuje kolejno:

- `npm --prefix frontend run check`,
- `npm --prefix frontend run build`,
- `python -m compileall backend`,
- `python -m unittest backend.test_smoke_endpoints`.

Smoke test backendu obejmuje krytyczne endpointy: dashboard globalny, listę i wycenę portfeli, create/buy/sell, transfery budżet ↔ inwestycje, harmonogram kredytu, radar i symbol map.

