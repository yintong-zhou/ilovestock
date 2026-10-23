---
type: handoff
date: 2026-10-23
status: pronto per il prossimo lavoro
seq: 4
prev: docs/handoff/2026-10-22-fundamental-screener.md
tags: [ilovestock, screener, review, codex, finviz, web, pypi]
---

## Obiettivo

`ilovestock` è uno strumento educativo, non consulenza finanziaria. Usa l'analisi fondamentale e tecnica
per valutare il potenziale dei titoli USA: dà un verdetto BUY / NO-BUY con piano di trade e
ha uno screener dei fondamentali. Lo usa da CLI e da una web app locale. Questa sessione ha messo in
sicurezza lo screener con tre review Codex e una `/code-review high`, e l'ha portato su main. Il
prossimo lavoro voluto dall'utente è **migliorare la navigazione e l'uso della web app**.

## A che punto siamo

- **main allineato a origin, ultimo commit `af1ffcb`.**
  - Lo screener è entrato con la PR #1 (merge `3e3f642`).
  - In locale c'è solo `main`.
  - Il branch remoto `origin/feature/fundamental-screener` esiste ancora: l'utente non ha deciso
    se cancellarlo.
- **Verifiche passate al commit `f1ec184`:**
  - `pytest -m "not slow"` passa con 242 test;
  - `ruff check` e `ruff format --check` sono puliti;
  - in `web/`, `npm run lint` e `npm run build` sono puliti.
  - `af1ffcb` tocca solo la documentazione.
- **Verificato dal vivo, con il permesso dell'utente:** tre richieste allo screener Finviz.
  - `o=-marketcap` ordina davvero;
  - `r=16` parte dalla riga 16;
  - con i filtri di default i risultati sono 119.
- **Mai eseguito:** un `ilovestock screen` reale completo. Non sappiamo ancora quanti candidati
  micro/small/mid produce il nuovo pre-filtro senza il filtro dividendi.
- **`CLAUDE.md` creato** con comandi, architettura, regole e insidie.
- **PyPI tolto dagli obiettivi:** README installa dal clone, roadmap aggiornata, memoria salvata.
- **Rimasti aperti dalla `/code-review high`** (decide l'utente):
  - **2.** Un errore Yahoo sui fondamentali va in `note`, quindi lo screener conta il titolo
    tra gli errori e non lo salva in cache. Questo va contro la correzione 1 della prima review
    Codex.
  - **3.** Se Finviz non restituisce righe, `screener_rows` alza `FinvizError`, quindi exit 1 / HTTP
    422 invece di "0 candidati". Questo va contro l'ultima review Codex. Per distinguere "zero
    risultati" da "pagina cambiata" bisogna vedere dal vivo come Finviz mostra una ricerca vuota.
  - **Pulizie:**
    - 6: `revokeObjectURL` subito dopo `a.click()` in `Screener.tsx`;
    - 8: i rank si calcolano due volte (`screen()` e `scores()`);
    - 9: il ciclo di paging è duplicato tra `screener_tickers` e `screener_rows`;
    - 10: `TooManyResults.total` non è più usato in produzione.
- **Rinviati dall'handoff precedente, ancora aperti:**
  - `-0.0 pt`;
  - un `--out` non scrivibile produce un traceback.

## Cosa abbiamo provato che NON ha funzionato

- **Un filtro di capitalizzazione Finviz con il tetto superiore.** Lo screener accetta una sola
  opzione `cap_*` e l'intervallo libero ("frange") è solo Elite: si vede nel JSON delle opzioni
  dentro `tests/fixtures/finviz_screener_default.html`. Sostituito con l'ordinamento per
  capitalizzazione.
- **Correggere il confine $50M usando uno scaglione "sotto nano_max".** Non esiste uno scaglione
  sotto "over $50M", quindi avrebbe tolto il filtro e fatto entrare tutte le nano. Scartato.
- **Pagine consecutive da 20 su una lista ordinata dal vivo.** Un titolo che sale tra due richieste
  sparisce. Ora le pagine si sovrappongono di 5 righe.
- **Controllo d'ordine tra una pagina e l'altra (`cap > last`).** Dava falsi errori quando i prezzi
  si muovevano. Ora l'ordine si controlla solo dentro ogni pagina.
- **Codex con thread nuovo** (`task-mvkr0392-9z75fg`): fallito con "Your workspace is out of
  credits". Senza crediti, le review vanno fatte con `/code-review` o con un revisore Claude.
- **Forwarder `codex:codex-rescue` in background:** a volte restituisce un suo riepilogo invece
  dell'output del companion. Il risultato vero si legge con
  `node ".../codex-companion.mjs" status` e poi `result <task-id>`. Un `/codex:result` senza ID ha
  restituito il job precedente mentre il nuovo era ancora in corso.
- **Test su un generatore infinito lanciato prima della correzione:** pytest resta appeso
  all'infinito, e c'è voluto `TaskStop`. Lanciare la suite con `timeout 120`.
- **`pytest.mark.parametrize` con l'HTML intero della pagina come parametro:** ID dei test enormi e
  output da 2 MB. Usare `ids=[...]`.
- **Un mock rimasto su `screener_tickers` mentre il codice usava `screener_rows`:** un test ha fatto
  richieste Finviz reali senza permesso. Ora `tests/conftest.py` blocca `requests.Session.send`
  fuori dai test `slow`.

## Problemi incontrati e come li abbiamo risolti

- **Uno snapshot fallito (429) restava in cache tutto il giorno.**
  - Sintomo: per tutto il giorno il titolo risultava "errore".
  - Correzione: `CachedProvider` non salva i fondamentali con `note` valorizzato.
  - Ora `note` contiene sia "Finviz error" sia "Yahoo error".
- **La lib `finviz` non riscaricava mai una pagina.**
  - Causa: `finviz.main_func.STOCK_PAGE` è un dizionario che non si svuota mai.
  - Correzione: `FinvizProvider` fa `pop` del ticker in un `finally`.
- **`serve` restava fermo al giorno di avvio.**
  - Causa: `FinvizProvider.today` era fissata in `__init__`.
  - Correzione: ora è una proprietà.
- **Un errore della ricerca web andava perso se si cambiava pagina.** Ora `screenError` vive in
  `App` accanto a `screening`. Verificato nel browser.
- **`#analysis/...` cambiava ma la pagina Analysis mostrava ancora i ticker vecchi.** Ora c'è
  `key={arg}` su `<Analysis>`. Verificato nel browser.
- **Un hook ("Fact-Forcing Gate") blocca la prima modifica di ogni file.** Chiede di dichiarare i
  fatti (chiamanti, schema, istruzione dell'utente) prima di procedere. In un batch parallelo alcune
  modifiche passano e altre no: dopo un blocco, controllare quali sono state applicate prima di
  riprovare.

## Decisioni prese

- **Pre-filtro:** niente filtro dividendi (Finviz usa la stima futura, la regola gli ultimi 12 mesi)
  e niente filtro di capitalizzazione. Le righe arrivano ordinate per capitalizzazione decrescente:
  si saltano large e giant e ci si ferma alla prima nano, con le stesse fasce della regola.
  - Scartati: "solo commenti" e "togliere solo `fa_div_none`".
- **Tetti:**
  - `MAX_CANDIDATES` (100) conta solo micro, small e mid.
  - `MAX_ROWS` (1000) limita le righe lette prima della prima nano, cioè circa 70 pagine al
    massimo.
  - Scartato: un tetto basso sulle pagine senza aver misurato quante sono le large/giant.
- **Pagina illeggibile:** se manca il contatore, se non ci sono righe, se righe e ticker non
  coincidono o se la pagina non parte dalla riga richiesta, la ricerca si ferma con un errore.
  Scartato: restituire una lista parziale.
- **Prezzi nello screen (decisione dell'utente):** si leggono prima i fondamentali, e con `note`
  valorizzato non si scaricano i prezzi. Poi si scarica un solo anno (`SCREEN_PERIOD = "1y"`), in un
  file di cache separato (`history1y`).
  - Conseguenza accettata: un `analyze` subito dopo lo screen riscarica i suoi 2 anni.
- **Gruppo di un solo titolo:** una misura N/D vale 0 anche quando il titolo è da solo (spec
  aggiornata). Scartato: "un titolo da solo vale sempre 100".
- **Errori di download:** un fallimento Yahoo conta come errore (correzione 1 di Codex), e zero
  righe da Finviz sono un errore (ultima review Codex). La code review suggerisce il contrario su
  entrambi: decide l'utente.
- **PyPI:** niente pubblicazione. L'installazione parte dal clone: build della UI, poi
  `pip install .`.
- **Branch:** in locale solo `main`.

## File toccati

- `src/ilovestock/providers/`:
  - `finviz.py`:
    - Finviz e Yahoo scrivono in `notes`;
    - `pop` di `STOCK_PAGE`;
    - `today` diventa una proprietà;
    - `_pct` gestisce i valori non finiti;
    - nuove funzioni `parse_screener_rows`, `first_row_number`, `screener_rows`;
    - nuova costante `OVERLAP`;
    - `parse_screener_page` dà errore se manca il contatore.
  - `cache.py`: non salva gli snapshot con `note`; un file di cache per ogni periodo di history.
  - `base.py`: `HISTORY_PERIOD`, e il protocollo `history(ticker, period)`.
  - `yahoo.py`: `history(period)`.
- `src/ilovestock/screener.py`:
  - via `fa_div_none` e il filtro di capitalizzazione;
  - `BY_CAP_DESC`, `candidates()`, `ALLOWED_BANDS`, `MAX_ROWS`, `SCREEN_PERIOD`;
  - nel ciclo, prima i fondamentali e poi i prezzi.
- `src/ilovestock/analysis.py`: `quality` calcolata dentro il `try`.
- `src/ilovestock/quality.py`: arrotondamento dopo la sottrazione.
- `src/ilovestock/models.py`: commento di `note`.
- `web/src/`:
  - `App.tsx`: `screenError` e `runScreen` (che ora chiama `onApiError`), più
    `<Analysis key={arg}>`;
  - `pages/Screener.tsx`: prop `error`, testo dello score.
- `tests/`:
  - `conftest.py`: blocco della rete;
  - `test_providers.py`: `fake_pages` e `cap_page` per le pagine sintetiche ordinate per
    capitalizzazione;
  - aggiunte in `test_screener.py`, `test_quality.py`, `test_rules.py`, `test_api.py` e
    `test_cli.py`.
- `README.md`: limiti dello screener, installazione dal clone, PyPI tolto.
- `CLAUDE.md` (nuovo).
- `docs/superpowers/specs/2026-10-22-fundamental-screener-design.md`: correzioni datate 2026-10-23.

## Dove vogliamo andare

1. **Migliora la navigazione e l'uso della web app.**
   1. Parti da un brainstorming con l'utente (skill `superpowers:brainstorming`): cosa è scomodo
      oggi, in quali pagine e in quali flussi. Per esempio Screener → "Analyze these" → Analysis,
      Dashboard, History.
   2. Prima di toccare la UI leggi `brand-guidelines.md`.
   3. Ogni cambiamento va verificato nel browser con il server offline (ricetta qui sotto).
2. Poi, se l'utente lo chiede:
   - i punti 2, 3, 6, 8, 9 e 10 della code review;
   - un primo `ilovestock screen` reale per misurare i candidati (richiede il permesso, perché fa
     richieste a Finviz e Yahoo).
3. Dopo: Portfolio (fase 2), partendo da un brainstorming.

## Da sapere prima di toccare qualcosa

- **Comandi in Git Bash:** `.venv/Scripts/pytest.exe`, `.venv/Scripts/ruff.exe` e
  `.venv/Scripts/python.exe`, con il `.exe` esplicito. Per la suite usa
  `timeout 120 .venv/Scripts/pytest.exe -m "not slow" -q`. Con l'output Rich usa
  `PYTHONIOENCODING=utf-8`.
- **Richieste dal vivo:** ogni richiesta a Finviz o Yahoo (prove reali, fixture, `-m slow`) va
  chiesta prima all'utente. Il blocco in `conftest.py` copre `requests` ma non `curl_cffi` di
  yfinance: per Yahoo nei test serve sempre `fake_yf`.
- **Server offline per provare la UI:** lo script non resta, va riscritto nello scratchpad.
  - Usa `create_app(pin_path=tmp/"pin.json", config_path=..., history_path=..., provider=...)`,
    con `PinStore(tmp/"pin.json").set("4821")` e `screener.screen` sostituito da una funzione finta.
  - Lancialo con `USERPROFILE` puntato su una cartella temporanea e con `uvicorn.run` su
    `127.0.0.1`.
- **Browser (chrome-devtools MCP):** apri la pagina con `isolatedContext`. Per inviare un form usa
  il tasto `Enter`. La route si cambia con `location.hash` da `evaluate_script`.
- **Pagine Finviz registrate:** quelle in `tests/fixtures/` sono ordinate per ticker, non per
  capitalizzazione. Per testare `screener_rows` costruisci le pagine con `cap_page`.
- **Codex:** il workspace è senza crediti. Per una review usa `/code-review` o un revisore Claude.
- **Handoff vecchi:** quelli del 2026-10-21 e del 2026-10-22 indicano ancora l'upload su PyPI come
  passo successivo. Ignoralo: l'utente l'ha tolto dagli obiettivi.
- **`directives/`:** non creare file lì senza chiedere (`AGENT.md`).
