---
type: handoff
date: 2026-10-23
status: pronto per review (branch su origin, PR non ancora aperta)
seq: 5
prev: docs/handoff/2026-10-23-screener-reviews.md
tags: [ilovestock, web, history, dashboard, watchlist, ux]
---

## Obiettivo

`ilovestock` è uno strumento educativo, non consulenza finanziaria. Usa l'analisi fondamentale e tecnica
per valutare il potenziale dei titoli USA: dà un verdetto BUY / NO-BUY con piano di trade e
ha uno screener dei fondamentali. Si usa da CLI e da una web app locale. Questa sessione ha
lavorato su **navigazione e uso della web app**, partendo da quello che l'utente trova scomodo
quando la usa.

## A che punto siamo

- **Branch `feature/web-watchlist-dashboard`**, pushato su origin, con working copy pulita.
  - `9286ea6`: Watchlist e Dashboard basata sulla history (commit mio).
  - `ce0f1cf`: riga intera cliccabile (commit dell'utente).
  - Il branch parte da `e8395c9`.
- **`main` locale** è avanti di 1 rispetto a origin, con `e8395c9`, un commit dell'utente non
  pushato. Contiene il messaggio del PIN, i filtri e le pagine della History e l'handoff
  precedente.
- **PR non aperta, merge non fatto:** decide l'utente.
- **Verifiche passate sull'ultimo stato:**
  - `pytest -m "not slow"`: 243 test;
  - `ruff check` e `ruff format --check` puliti;
  - `npm run lint` e `npm run build` puliti.
- **Tutto provato nel browser con il server offline**, senza richieste a Finviz o Yahoo:
  - login: con un PIN sbagliato o corto compare "Wrong PIN. Try again." invece del JSON;
  - History: filtri, pagine 25/50, ritorno all'ultima pagina valida dopo una cancellazione, stato
    vuoto, layout mobile;
  - Dashboard;
  - Watchlist: Refresh, errore di Refresh, Remove, pulsanti Add/Remove in Analysis e History;
  - clic sulla riga in History, Watchlist, Dashboard, Analysis e Screener.
- **Non fatto e ancora aperto:**
  - **Cambio PIN in Settings:** con un PIN corto mostra ancora il JSON di Pydantic. L'ho
    proposto due volte e l'utente non ha deciso.
  - **Punti della `/code-review high`:** 2, 3, 6, 8, 9 e 10 (vedi l'handoff precedente).
  - **Rinviati:** `-0.0 pt` e un `--out` non scrivibile.
  - **Mai fatto:** un `ilovestock screen` reale. Serve il permesso dell'utente.
  - **Portfolio:** fase 2.
  - **Branch remoto `origin/feature/fundamental-screener`:** l'utente non ha ancora deciso se
    cancellarlo.
- **Non rifinito:** su mobile il filtro della History va su due righe senza separatore
  orizzontale. Accettabile, non sistemato.

## Cosa abbiamo provato che NON ha funzionato

- **Esportare funzioni helper (`rowClick`, `toHistory`) da `components.tsx`.** Fallisce il lint
  `react-refresh/only-export-components`, perché da lì si possono esportare solo componenti e
  costanti. Gli helper ora stanno in `web/src/format.ts`.
- **Correggere il JSON del PIN in `api.ts` per tutti i 422.** Usare i `msg` di Pydantic
  produrrebbe "String should match pattern '^\d{4,8}$'", che è ancora codice. Il messaggio
  semplice è nella `PinScreen` (401/422 → "Wrong PIN. Try again."), mentre 429 ed errori di rete
  tengono il loro testo.
- **`navigate_page` di chrome-devtools con solo l'hash diverso.** Non ricarica la SPA: lo stato
  resta e la history non si rilegge. Per ricaricare usa `location.reload()` da `evaluate_script`.
- **`location.reload()` dentro uno script che poi continua.** Dà "Execution context was
  destroyed". Fai il reload in uno script a parte, con `setTimeout(() => location.reload(), 50)`,
  e i controlli nello script successivo.
- **Aprire la pagina prima che uvicorn sia pronto.** Dà `ERR_CONNECTION_REFUSED` e resta una tab
  di errore con un altro `pageId`. Aspetta il server con un ciclo `curl` prima di `new_page`.
- **Test di cancellazione con la dimensione pagina rimasta a 50.** Lo stato della pagina persiste
  tra uno script e l'altro, e ho cancellato tutti i ticker filtrati della history finta. Prima di
  un test, rimetti lo stato o rigenera i dati.

## Problemi incontrati e come li abbiamo risolti

- **JSON al login.**
  - Causa: un PIN di meno di 4 cifre produce un 422 di Pydantic con `detail` come lista, e
    `api.ts` lo trasforma con `JSON.stringify`.
  - Correzione: messaggio fisso nella `PinScreen`. Lo stesso problema resta nel cambio PIN in
    Settings.
- **"Rows per page" su tre righe.** Corretto con `whitespace-nowrap` sull'etichetta.
- **Errore di Refresh nella Watchlist su un ticker senza analisi salvate.** Il messaggio diceva
  "the last saved analysis is still shown". Ora quella frase compare solo se l'analisi esiste.
- **Hook "Fact-Forcing Gate".** Blocca ancora la prima modifica di ogni file e la prima creazione
  di ogni file, anche nello scratchpad.
  - Prima di riprovare dichiara i fatti: chiamanti, schema dei dati, istruzione dell'utente.
  - Conta solo una ricerca fatta con Glob o Grep in un turno precedente, non nello stesso batch.
  - In un batch parallelo alcune modifiche passano e altre no: controlla quali sono state
    applicate prima di riprovare.
- **Visual companion su Windows.**
  - Avvia `start-server.sh` con `run_in_background` e `--project-dir` sullo scratchpad, così il
    repo resta pulito.
  - Fermalo con `stop-server.sh <session_dir>`. L'exit 143 del task in background è normale.

## Decisioni prese

- **Filtro della History: variante B.**
  - Scelta: un controllo a quattro opzioni (All tickers, Fundamentals all PASS, Technical all
    PASS, Both) e due colonne con i quadratini e il conteggio `n/m`.
  - Scartata la A: due interruttori e una colonna sola.
  - La colonna "Previous" è stata tolta, e il cambio di verdetto resta nel dettaglio del ticker.
- **Regole del filtro della History:**
  - Una riga per ticker, con l'analisi più recente, dalla più recente.
  - "All PASS" è severo: un N/D esclude il ticker.
  - "Next earnings" conta come fondamentale (come in Analysis e Dashboard), "After last
    earnings" come tecnico.
  - Il raggruppamento divide i criteri salvati in corrispondenza di "Next earnings" (`groups()`).
    Scartato: cambiare l'API o il CSV.
- **Paginazione della History:**
  - Lato client, 25 righe predefinite oppure 50.
  - Pagina 1 quando cambiano filtro o dimensione.
  - Ritorno all'ultima pagina valida dopo una cancellazione.
  - Filtro e pagina restano tra `#history` e `#history/T`.
- **Dashboard: legge la history** (ultima analisi per ticker), non più l'ultima analisi della
  sessione.
  - Tolti il riquadro "Data errors" (la history non salva gli errori) e la riga del disclaimer,
    che la sidebar mostra già.
  - Mostra i 10 ticker più recenti con il link "See all in History".
- **Watchlist:**
  - **Dove sta:** una pagina sua nella barra laterale, non una sezione della Dashboard.
  - **File:** `~/.config/ilovestock/watchlist.txt`, testo semplice con un ticker per riga, nello
    stesso formato di `analyze --watchlist`. Scartato un JSON con date e note.
  - **Limite:** 50 titoli (= `inputs.MAX_TICKERS`).
  - **Refresh:** rifà l'analisi sull'ultima chiusura. È una decisione dell'utente ("ultima
    chiusura"). Scartato il prezzo live da Yahoo.
  - **Pulsanti:** Refresh solo per riga, senza "Refresh all", e Remove senza conferma.
  - **Stato:** `WatchButton` legge la lista da solo. Scartato tenerla nello stato di `App`.
- **Riga cliccabile:**
  - Il clic fa quello che fa il nome del ticker: apre lo storico, oppure apre e chiude il
    dettaglio in Analysis e Screener.
  - Esclusi i controlli dentro la riga e la selezione di testo.
  - Il nome resta il target da tastiera.
- **Processo:**
  - Dashboard e Watchlist descritte in chat e confermate dall'utente, senza documento di design.
  - Il lavoro sta su un feature branch, come la PR #1.

## File toccati

- `web/src/PinScreen.tsx`: messaggio "Wrong PIN. Try again." per 401/422 (in `e8395c9`).
- `web/src/pages/History.tsx`: `TickerList` con filtro a quattro viste, colonne
  Fundamental/Technical, paginazione e stato `view` in `History`; `WatchButton` nell'intestazione
  del ticker; riga cliccabile.
- `web/src/pages/Dashboard.tsx`: riscritta sulla history (`latestByTicker`), prop `onApiError`.
- `web/src/pages/Watchlist.tsx` (nuovo): tabella, Refresh, Remove, errori per riga.
- `web/src/pages/Analysis.tsx`: `WatchButton` nel dettaglio, `Detail` riceve `onApiError`, riga
  cliccabile.
- `web/src/pages/Screener.tsx`: riga cliccabile.
- `web/src/components.tsx`: `RuleGroup` (quadratini + `n/m`), `WatchButton`; le celle di
  `RuleMatrix` sono ora un helper di modulo condiviso.
- `web/src/format.ts`: `when`, `groups`, `latestByTicker`, `rowClick`, `toHistory`.
- `web/src/api.ts`: `watchlist()`, `watch()`, `unwatch()`.
- `web/src/App.tsx` e `web/src/Sidebar.tsx`: pagina `watchlist`, e la Dashboard non riceve più
  `lastRun`.
- `src/ilovestock/watchlist.py` (nuovo): `read`, `add`, `remove`, `MAX`, lock di thread, scrittura
  atomica.
- `src/ilovestock/api/app.py`: `create_app(watchlist_path=...)`, route `GET/PUT/DELETE
  /api/watchlist[/{ticker}]` che restituiscono la lista intera.
- `tests/test_api.py`: `test_watchlist_api`, e la fixture `client` passa `watchlist_path`.
- `README.md`: sezione "Pages" aggiornata e nuova voce "Watchlist".
- `CLAUDE.md`: `watchlist.txt` aggiunto tra i file accanto alla config.

## Dove vogliamo andare

1. **Chiedi all'utente come integrare `feature/web-watchlist-dashboard`:** PR verso `main`, oppure
   merge locale. Ricorda che `main` locale ha `e8395c9` non pushato, e che il branch lo include.
2. **Proponi di nuovo la correzione del JSON nel cambio PIN in Settings** (422 con PIN corto), sul
   modello della `PinScreen`.
3. **Continua a migliorare la web app con l'utente.** Chiedi qual è il prossimo punto scomodo:
   - Possibili spunti: "Refresh all" nella Watchlist e il filtro della History su mobile.
   - Ogni cambiamento va verificato nel browser con il server offline.
4. **Poi, se l'utente lo chiede:**
   - i punti 2, 3, 6, 8, 9 e 10 della code review, `-0.0 pt` e `--out`;
   - un primo `ilovestock screen` reale, con permesso;
   - Portfolio (fase 2), partendo da un brainstorming.

## Da sapere prima di toccare qualcosa

- **Server offline per la UI.** Lo script non resta, va riscritto nello scratchpad.
  1. Prima di `create_app`, sostituisci `ilovestock.api.app.analyze_many` e
     `ilovestock.api.app.screener.screen` con funzioni finte. Lo screen finto restituisce un
     oggetto con `candidates`, `passed`, `errors` e `hits` (`ScreenHit`).
  2. Chiama `create_app(pin_path, config_path, history_path, watchlist_path, provider=object())`
     con `PinStore(...).set("4821")`.
  3. Lancia `uvicorn.run` su `127.0.0.1:3999` con `USERPROFILE`/`HOME` su una cartella
     temporanea.
  4. Per la history finta, scrivi un CSV con `history.FIELDS` e `history._to_csv(row)`, con
     `criteria` nell'ordine fondamentali, "Next earnings", tecnici.
  5. Nel browser, sblocca con `fetch('/api/pin/unlock', …)` e poi ricarica in uno script a parte.
- **Refresh nella Watchlist durante la seduta di New York dà lo stesso risultato.** I prezzi
  intraday sono in cache e la barra di oggi viene scartata. Non è un bug.
- **`groups()` assume che "Next earnings" sia nei criteri salvati.** È sempre vero, perché la
  history non salva le analisi con errore e ogni analisi riuscita ha il criterio earnings.
- **`History` non ha una `key` in `App`.** Il suo stato sopravvive tra `#history` e `#history/T`,
  ma la history si carica solo al mount.
- **`format.ts` contiene anche helper che non formattano.** È così perché `components.tsx` può
  esportare solo componenti (regola di lint).
- **Comandi:** `timeout 120 .venv/Scripts/pytest.exe -m "not slow" -q`, poi
  `.venv/Scripts/ruff.exe`, poi `cd web && npm run lint && npm run build`.
- **Rete:** ogni richiesta dal vivo a Finviz o Yahoo va chiesta prima all'utente.
- **Git:** chiedi prima di ogni `git push`. L'utente a volte fa commit e push da solo tra un
  turno e l'altro, quindi controlla `git log` prima di proporre un commit.
