---
type: handoff
date: 2026-10-20
status: superato
seq: 1
prev: nessuno
tags: [ilovestock, cli, web-app, finviz, pin, m6, m7]
---

> **Aggiornamento 2026-10-21.** Questo file è la fotografia del 20/10. Da allora, su `main`:
> CI verde (fix `pythonpath` di pytest), UI compilata in `src/ilovestock/static` e inclusa nel
> pacchetto (non più `web/dist`), `CONTRIBUTING.md` e screenshot AAPL nel README, correzioni
> dell'audit Codex (verdetto `BUY*` con `--allow-missing`, solo prezzi in USD, cache per sessione
> di New York, PIN impostato nel terminale da `ilovestock serve`, niente CORS). I numeri dei
> test qui sotto sono di quella data. Per il server di prova: imposta il PIN con
> `PinStore(path).set(...)` prima di avviarlo, perché l'API non permette più di crearlo.

## Obiettivo

`ilovestock`: strumento educativo (non consulenza finanziaria) che applica il metodo del corso
"Investire in azioni nel lungo termine" a titoli USA e dà un verdetto BUY / NO-BUY con un piano di
trade (entry, stop, target, numero di azioni). Due interfacce sullo stesso core Python: CLI
(Typer + Rich) e web app locale (FastAPI + React), come chiedono `AGENT.md` e `PROJECT.md`. Il
motivo: a mano il metodo richiede ~7 filtri fondamentali, 4 indicatori e il calcolo della
posizione; gli screener non hanno Donchian 10w e ADX 18d.

## A che punto siamo

- **Fatti e su `origin/main` (commit `3b4b2dc`):** M0–M6, cioè dati con cache, indicatori,
  regole, piano di trade, input (ticker, watchlist, screener Finviz), config TOML, export
  MD/CSV/JSON, output CLI in inglese, esclusione della barra giornaliera parziale.
- **Fatto ma NON committato:** web app completa e nuova grafica scura. Contiene il backend
  (`src/ilovestock/api/`), i comandi `ilovestock serve` e `ilovestock pin reset`, il frontend
  in `web/`, `tests/test_api.py`, il job CI per il frontend e il README aggiornato.
- **Verifiche passate:** `ruff check .`, `ruff format --check .`, `pytest -m "not slow"`
  (137 test), `npm run lint`, `npm run build`. Web app provata nel browser su un server di
  prova a 1440px e 375px.
- **Non iniziato:** M7 (release), Portfolio (fase 2), storico delle analisi per la Dashboard.
- **Mai eseguiti:** la CI su GitHub (non ho guardato il primo run) e il test `slow`
  (`pytest -m slow`, interroga Finviz dal vivo: va chiesto all'utente prima).

## Cosa abbiamo provato che NON ha funzionato

- **Screener della libreria `finviz` 2.0.0** (`Screener.init_from_url`): restituisce sempre
  `NoResults`, perché il sito Finviz ha cambiato il markup del conteggio dei risultati. Sostituito
  da un parser nostro dei link `/quote?t=` con paginazione `r=1,21,...` in
  `providers/finviz.py`. `finviz.get_stock` invece funziona ancora.
- **pandas-ta come riferimento per i test degli indicatori:** non è installabile su PyPI con
  Python 3.13. Usato TA-Lib (`ta-lib` 0.8.2, wheel disponibili), solo come dipendenza dev.
- **Data earnings da Finviz come unica fonte:** il campo `Earnings` ("Jul 23 BMO") non ha l'anno
  e resta sull'ultimo report finché il prossimo non è annunciato. Una data passata viene ignorata
  e si usa quella di Yahoo.
- **Dividendo da Finviz come unica fonte:** `-` vuol dire sia "nessun dividendo" sia "dato
  mancante". In quel caso il dividend yield si calcola dalla colonna `Dividends` dello storico
  Yahoo.
- **Screenshot del browser con la finestra di Claude nascosta:** vanno in timeout. Usare
  `get_page_text` o `find`, oppure chiedere di portare la finestra in primo piano.
- **Navigazione del browser integrato verso `http://127.0.0.1:8765`:** a volte rifiutata. Con
  `http://localhost:8765` funziona.

## Problemi incontrati e come li abbiamo risolti

- **Rich interpretava come markup il testo dei dati.** Sintomo: rischio di crash o testo sparito
  con stringhe tra parentesi quadre (es. errori Finviz). Correzione: `rich.markup.escape` su
  valori, note e motivi in `report.py`.
- **Valori numpy nei criteri.** Sintomo: warning di serializzazione di Pydantic nell'API.
  Correzione: `CriterionResult.__post_init__` converte i valori numerici in `float`.
- **CSS globale che annullava Tailwind.** Sintomo: i margini dei titoli (`mt-8`) non avevano
  effetto. Causa: in Tailwind 4 le regole CSS fuori dai layer battono le classi di utilità.
  Correzione: regole base dentro `@layer base` in `web/src/index.css`.
- **Lint `react-refresh/only-export-components`.** Sintomo: errore su `components.tsx`.
  Correzione: la funzione `fmt` spostata in `web/src/format.ts`.
- **Cache con un formato vecchio.** Sintomo: file cache scritti da una versione precedente.
  Correzione: `CachedProvider.fundamentals` riscarica i dati se il JSON non si carica.
- **Barra giornaliera parziale.** Sintomo: a mercato aperto Yahoo include il giorno in corso.
  Correzione: `drop_partial_bar` in `providers/yahoo.py` (prima delle 16:00 di New York).

## Decisioni prese

- **Fonte dei fondamentali:** Finviz, con Yahoo come fallback per ogni singolo campo; la fonte è
  indicata nella nota di ogni criterio. Scartato: Yahoo principale con Finviz solo per gli
  istituzionali (preferenza dell'utente).
- **Crescita:** default `yoy` da Finviz. `qoq` (quello del corso) si calcola dai trimestri Yahoo.
  Scartato: `qoq` come default, perché i campi Finviz "Q/Q" sono in realtà YoY.
- **`finviz`:** dipendenza obbligatoria. Scartato: extra facoltativo `[finviz]` (D10).
- **Licenza:** GPL-3.0 (D9). Scartate: MIT e Apache-2.0.
- **D1 ROE:** si confronta il livello (> 15%). Scartato: variazione trimestre su trimestre.
- **D7 consolidamento:** solo informativo. Scartato: criterio bloccante.
- **D5 stop:** minimo più basso delle 10 settimane precedenti. **D6 entry:** breakout = ultima
  chiusura, pullback = banda superiore Donchian, restart = massimo della settimana precedente.
- **Crescita EPS con trimestre di confronto ≤ 0:** risultato `N/D`. Scartati: FAIL e crescita
  calcolata su base assoluta.
- **`--allow-missing`:** salta solo gli N/D dei fondamentali. Earnings e tecnici N/D bloccano
  sempre.
- **Accesso web:** PIN di 4–8 cifre (hash PBKDF2), cookie di sessione HttpOnly in memoria, blocco
  di 30 secondi dopo 5 errori, `TrustedHostMiddleware`, ascolto solo su 127.0.0.1. Scartato: un
  sistema di account (l'utente non lo vuole).
- **Stack web:** React 19, Vite 8, TypeScript, Tailwind 4, font locali con fontsource, routing
  con l'hash dell'URL senza libreria di routing. Scartato: Google Fonts (l'app è locale).
- **Grafica:** tema scuro con la palette del brand e una "matrice delle regole" come elemento
  distintivo. L'utente non ha ancora confermato scuro rispetto a chiaro: il tema chiaro è stato
  offerto come alternativa.
- **Dashboard:** statistiche solo dell'ultima analisi della sessione, non salvate. **Portfolio:**
  pagina segnaposto fino alla fase 2.
- **Commit:** direttamente su `main`, con autore `zhouyintong96@gmail.com` (impostato nella
  config git locale del repo).

## File toccati

Solo quelli non ancora committati:

- `src/ilovestock/api/app.py`: FastAPI con PIN, config, analisi e frontend statico.
- `src/ilovestock/api/pin.py`: `PinStore`, `Throttle`, `Sessions`.
- `src/ilovestock/cli.py`: comandi `serve` e `pin reset`; l'analisi passa da `analyze_many`.
- `src/ilovestock/analysis.py`: nuova funzione `analyze_many` (benchmark e ciclo sui ticker),
  condivisa da CLI e API.
- `src/ilovestock/models.py`: valori dei criteri convertiti in `float`.
- `pyproject.toml`: aggiunte `fastapi` e `uvicorn`, più `httpx` tra le dipendenze dev.
- `.github/workflows/ci.yml`: job `web` (npm ci, lint, build).
- `README.md`: sezione "Web app" e comandi di sviluppo del frontend.
- `tests/test_api.py`: 18 test su PIN, throttle, host, config e analisi.
- `web/`: `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`,
  `eslint.config.js`, `index.html` e `src/`:
  - `App.tsx`, `Sidebar.tsx`, `PinScreen.tsx`
  - `components.tsx`, `format.ts`, `api.ts`, `types.ts`, `index.css`, `main.tsx`
  - `pages/Dashboard.tsx`, `pages/Portfolio.tsx`, `pages/Analysis.tsx`, `pages/Settings.tsx`
- `docs/handoff/2026-10-20-cli-and-web-app.md`: questo file.

## Dove vogliamo andare

1. Lancia di nuovo le verifiche: `ruff check .`, `ruff format --check .`,
   `pytest -m "not slow"`, e in `web/` `npm run lint` e `npm run build`. Poi committa e
   pusha su `main` (git user già `zhouyintong96@gmail.com`; non usare `--no-verify`).
2. Controlla il primo run della CI su GitHub: Python 3.11 e TA-Lib su Linux non sono mai stati
   provati.
3. Inizia M7 (release):
   - aggiungi `CONTRIBUTING.md` e uno screenshot dell'output nel README;
   - verifica che `pip install` funzioni partendo da un repo pulito;
   - risolvi il percorso di `web/dist`, che oggi esiste solo in un checkout (`WEB_DIST` in
     `api/app.py`): va incluso nel pacchetto per un'installazione da PyPI.

## Da sapere prima di toccare qualcosa

- **Comandi:** usare `.venv/Scripts/python`, `.venv/Scripts/ruff`, `.venv/Scripts/ilovestock`
  (Windows, venv nella root). Il frontend si compila con `npm run build` dentro `web/`; il
  server serve `src/ilovestock/static` (vedi l'aggiornamento in cima).
- **Prove manuali della web app:** non usare `ilovestock serve` sul PIN reale dell'utente. Usa
  un server di prova con `create_app(pin_path=..., config_path=...)` in una cartella
  temporanea; quello di questa sessione era `scratchpad/serve_test.py` sulla porta 8765, con PIN
  di prova `4821`.
- **Cache:** sta in `~/.cache/ilovestock`, un file per giorno. Se cambi il formato dei dati,
  cancella i file del giorno.
- **Finviz:** scraping non ufficiale, ToS a rischio. Ogni nuova richiesta live (anche per
  registrare fixture) va chiesta all'utente. I test di default restano offline.
- **Regole fisse da `PROJECT.md`:** parametri degli indicatori costanti, `risk_pct` > 2
  rifiutato, R:R < 2 scartato, dato mancante sempre `N/D` e mai `PASS`.
- **Directive:** non creare file in `directives/` senza chiedere (`AGENT.md`).
- **Esposizione in rete:** non esporre il server oltre 127.0.0.1 senza conferma. Il PIN è un
  lucchetto locale, non un'autenticazione.
- **Warning nei test:** quello di deprecazione `httpx` / Starlette viene dalla libreria; si può
  ignorare.
