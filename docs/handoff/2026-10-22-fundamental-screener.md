---
type: handoff
date: 2026-10-22
status: in-corso
seq: 3
prev: docs/handoff/2026-10-21-audit-history-release.md
tags: [ilovestock, screener, qualità, finviz, cache, pypi]
---

## Obiettivo

`ilovestock` è uno strumento educativo, non consulenza finanziaria. Usa l'analisi fondamentale
e tecnica per valutare il potenziale dei titoli USA e dà un verdetto BUY / NO-BUY con un piano
di trade, da CLI e da web app locale. Questa sessione ha aggiunto uno **screener dei
fondamentali**. Prima l'utente cercava i titoli con uno screener esterno, che non ha gli stessi
criteri del metodo, e passava ad `analyze` liste piene di titoli destinati al NO-BUY.

## A che punto siamo

- **Su main, pushato:** commit `1f3829f`. README e pyproject sono pronti per PyPI, wheel e sdist
  0.1.0 sono in `dist/` (ignorata da git) e `twine check` passa.
  - **Non fatto:** l'upload su TestPyPI e PyPI. Lo fa l'utente con il suo token.
- **Branch `feature/fundamental-screener`:** 11 commit sopra main, non pushato né mergiato.
  Working tree pulito, ultimo commit `1198cc4`.
  - Il design (`0ec44d6`) e il piano (`cb80cf4`) sono stati committati su main prima di creare il
    branch e non sono ancora pushati: **main è avanti di 2 commit rispetto a origin**.
  - **Cosa contiene:**
    - `ilovestock screen [--max N] [--out FILE]`;
    - la pagina web Screener;
    - `POST /api/screen`;
    - la riga Quality informativa in `analyze --detail` e nel dettaglio web.
  - **Verifiche:**
    - `pytest -m "not slow"` passa con 224 test;
    - `ruff check` e `ruff format --check` sono puliti;
    - in `web/`, `npm run lint` e `npm run build` sono puliti;
    - la review finale (Opus) è passata con 2 correzioni già committate (`402faf1`, `1198cc4`).
  - **Non verificato su dati reali:** l'utente ha detto no alla ricerca dal vivo (Task 9, passo 2).
- **Integrazione del branch:** l'ho chiesta (merge locale, push + PR, oppure lasciarlo così) e
  l'utente non ha ancora risposto.
- **Correzione della cache Finviz:** iniziata, ma **nessun file è stato modificato**. L'utente ha
  rifiutato una chiamata Bash di sola lettura (grep su lib e sorgenti) e poi ha chiesto questo
  handoff.
  - **Confermata nel codice** la causa 2: `.venv/Lib/site-packages/finviz/main_func.py`, dove
    `get_page` riscarica una pagina solo se il ticker non è già in `STOCK_PAGE`, e il dizionario
    non si svuota mai.
  - **Cause 1 e 3:** sono ancora da verificare nel codice prima di correggere.

## Cosa abbiamo provato che NON ha funzionato

- **Revisore finale su Fable 5.1:** HTTP 429, servono crediti a consumo. Usare `model: opus`.
- **Script Python inline lanciati dal tool Bash, con `"\n"` nel codice:** il tool riduce `\\` a
  `\` e il test diventava un a capo vero, cioè una SyntaxError. Per testo con backslash usare
  Edit o Write.
- **`ruff format --check .` con il piano Markdown committato su main:** ruff formatta anche i
  blocchi Python dentro i `.md`, quindi la CI sarebbe fallita. Ho formattato il file. I prossimi
  documenti con blocchi di codice vanno passati a `ruff format`.
- **Messaggio "Skipped for data errors" dentro il pannello della tabella:** il contenitore della
  tabella ha `-m-6` e ci finiva sopra. Spostato sotto il pannello.
- **Test `--max 51` che controllava solo il codice d'uscita 2:** passava anche prima che il
  comando esistesse ("No such command"). Ora controlla anche il testo `1<=x<=50`.
- **Ricerca del web con lo stato locale alla pagina:** se uscivi dalla pagina, "Search" tornava
  attivo e partiva una seconda ricerca. Inoltre il risultato ricompariva dopo il Lock. Ora la
  ricerca gira in `App`, con un contatore `locks`.

## Problemi incontrati e come li abbiamo risolti

- **Errore di Finviz su un singolo titolo (per esempio un 429).** Sintomo: il titolo risultava
  "non passa". Causa: `FinvizProvider` ripiega su Yahoo senza `inst_trans_pct`, che dà N/D.
  Correzione: in `screen()`, se `fund.note` è valorizzato il titolo va in `errors`.
- **Arrotondamento del punteggio diverso tra terminale e web.** Python arrotonda al pari (12.5
  diventa 12), `Math.round` per eccesso (12.5 diventa 13). Ora il terminale usa
  `int(score + 0.5)`.
- **`print` su stdout Windows (cp1252) con le tabelle Rich:** dà `UnicodeEncodeError`. Lanciare
  con `PYTHONIOENCODING=utf-8`.

## Decisioni prese

- **Universo:** tutte le azioni quotate su NASDAQ, NYSE e AMEX, ADR comprese, senza `geo_usa`.
  Scartato: solo aziende con sede negli USA.
- **Tetto dei candidati:** 100, senza misurare prima (decisione dell'utente). Con le soglie di
  default oggi sono 43. Scartati un job in background e un tetto più alto.
- **Punteggio di qualità:** ROIC più variazione del margine operativo a un anno, ognuno come
  percentile di posizione, poi la media. Scartati la crescita delle vendite (l'utente: "la
  vendita in sé non conta nulla"), la crescita dell'utile operativo (esplode da una base piccola)
  e l'EVA (il costo del capitale è troppo fragile da stimare).
- **Dove si vede la qualità:** opzione B, cioè nello screener e come riga INFO in `analyze`.
  Scartata A, solo nello screener.
- **Limite dei risultati:** default 20, massimo 50 (lo stesso limite di `analyze`).
- **`post_earnings`:** fuori dal filtro dello screener, perché è un'attesa di pochi giorni.
- **Titoli senza dati Finviz completi:** restano fuori, ed è dichiarato in README, help e pagina.
- **Lavoro sul branch nel checkout principale:** scelta dell'utente. Il worktree richiedeva un venv
  nuovo, perché l'installazione editabile punta qui.
- **Esecuzione del piano:** Native, con una sola review finale. Scartata Subagent-driven.
- **Correzione della cache:** l'utente ha detto "esegui qui". La card della sessione separata
  risulta già chiusa.

## File toccati

- `src/ilovestock/models.py`: `Fundamentals.roic_pct` e `.operating_income`, la dataclass
  `Quality` e `TickerAnalysis.quality`.
- `src/ilovestock/quality.py` (nuovo): `margin_change`, `quality`, `ranks` e `scores`.
- `src/ilovestock/screener.py` (nuovo):
  - filtri Finviz a scaglioni e `screener_url`;
  - `screen()`, `ScreenHit` e `ScreenResult`;
  - `MAX_CANDIDATES = 100`.
- `src/ilovestock/analysis.py`: `fundamental_checks`, condivisa da `analyze` e `screen`.
- `src/ilovestock/providers/finviz.py`: chiave `ROIC` ed eccezione `TooManyResults(message, total)`.
- `src/ilovestock/providers/yahoo.py`: riga `Operating Income`.
- `src/ilovestock/report.py`: `quality_text`, `screen_table` e la riga Quality in `detail()`.
- `src/ilovestock/cli.py`: comando `screen`.
- `src/ilovestock/api/app.py`: `ScreenIn`, `ScreenOut` e `POST /api/screen`.
- `web/src/`:
  - `pages/Screener.tsx` (nuovo);
  - `App.tsx` (route, stato `lastScreen`/`screening`, `runScreen`, `locks`), `Sidebar.tsx`,
    `types.ts`, `api.ts`, `format.ts` (`pct`, `points`, `qualityText`);
  - `components.tsx` (`CriteriaTable` con la prop `quality`);
  - `pages/Analysis.tsx` (prop `initialTickers`).
- `execution/record_fixtures.py`: modalità `--screen`.
- `tests/`:
  - `test_quality.py` e `test_screener.py` (nuovi);
  - aggiunte in `test_providers`, `test_rules`, `test_cli` e `test_api`;
  - fixture `fixtures/finviz_screener_default.html` (registrata dal vivo con il permesso
    dell'utente).
- `README.md`: installazione via pip, link assoluti e sezione "Find candidates". `PROJECT.md`:
  riga `screen`.
- `docs/superpowers/specs/2026-10-22-fundamental-screener-design.md` e
  `docs/superpowers/plans/2026-10-22-fundamental-screener.md`.

## Dove vogliamo andare

1. **Riprendi la correzione della cache Finviz** sul branch `feature/fundamental-screener`, o su
   un branch nuovo se l'utente preferisce. Per ognuno dei tre punti: prima un test che fallisce,
   offline, con i fake di `tests/conftest.py`.
   1. **`providers/cache.py`.** `CachedProvider.fundamentals` salva lo snapshot anche quando
      `note` contiene "Finviz error". Non salvarlo quando `f.note` è valorizzato. Test: un
      provider interno che restituisce `note="Finviz error: 429"` non deve produrre il file
      JSON, e una seconda chiamata deve tornare al provider interno.
   2. **`providers/finviz.py`.** Avvolgi `finviz.get_stock(ticker)` in un `try/finally` che fa
      `finviz.main_func.STOCK_PAGE.pop(ticker, None)`: la pagina si riscarica a ogni chiamata e la
      memoria non cresce. Test: un `get_stock` finto che imita la cache della lib (riempie
      `STOCK_PAGE` solo se il ticker manca); due chiamate di fila devono vedere due pagine diverse.
   3. **`providers/finviz.py`.** `FinvizProvider.today` è fissata in `__init__`, quindi su
      `serve` resta ferma al giorno di avvio. Rendila una proprietà che restituisce la data
      iniettata oppure `date.today()`. Test: sostituisci `ilovestock.providers.finviz.date` con
      una sottoclasse che ha `today()` controllabile e verifica che `fundamentals().fetched`
      segua il giorno.
2. Chiedi all'utente come integrare `feature/fundamental-screener`: merge locale, push + PR,
   oppure lasciarlo così. **Chiedi prima di ogni push** (riga 9 di `PROJECT.md`). Ricorda che
   anche main ha 2 commit non pushati.
3. Poi: l'upload su TestPyPI e PyPI lo fa l'utente (i comandi `twine` sono nella sessione
   precedente). Rigenera prima wheel e sdist se il codice cambia: `cd web && npm ci && npm run
   build`, poi `python -m build`.
4. Dopo: Portfolio (fase 2), partendo da un brainstorming.

## Da sapere prima di toccare qualcosa

- **Comandi in Git Bash:** `.venv/Scripts/pytest.exe`, `.venv/Scripts/ruff.exe` e
  `.venv/Scripts/python.exe`, con il `.exe` esplicito. Il venv è Python 3.13.
- **Finviz dal vivo:** ogni richiesta (prove reali, fixture, `pytest -m slow`) va chiesta prima
  all'utente.
- **Prove manuali senza toccare i dati reali:**
  - `USERPROFILE` puntato su una cartella temporanea, così config, cache e `history.csv` reali
    restano intatti;
  - per il server: `create_app(pin_path=..., config_path=..., history_path=..., provider=...)` e
    `PinStore(path).set("4821")`.
  - Lo script del server offline (`serve_screener_test.py`) era nello scratchpad della sessione e
    va riscritto. Usava `FakeTicker` e `fake_get_stock` di `tests/conftest.py` e uno
    `screener.screen` finto.
- **Browser della preview:** il tasto `Return` simulato non invia i form, `Enter` sì. Non è un bug
  della UI.
- **`ruff format --check .`:** controlla anche i file `.md` che contengono blocchi Python.
- **Cache del giorno:** dopo aver cambiato `Fundamentals`, i file JSON del giorno in
  `~/.cache/ilovestock` si caricano ancora (i campi nuovi hanno un default), ma hanno la Quality
  N/D fino al giorno dopo.
- **Problemi minori rinviati** dalla review (decide l'utente se farli):
  - con zero candidati Finviz il comando esce con 1 invece di 0;
  - `fa_div_none` usa la stima futura del dividendo;
  - nessun tetto superiore alla capitalizzazione nel pre-filtro, senza un commento che lo spieghi;
  - `-0.0 pt`;
  - un `--out` non scrivibile produce un traceback;
  - nessun test parsa la nuova fixture;
  - un titolo senza dati di qualità, se è da solo, prende 0.
- **`directives/`:** non creare file lì senza chiedere (`AGENT.md`).
