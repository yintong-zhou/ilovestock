---
type: handoff
date: 2026-10-21
status: pronto per la release
seq: 2
prev: docs/handoff/2026-10-20-cli-and-web-app.md
tags: [ilovestock, audit, history, pypi, m7]
---

## Obiettivo

`ilovestock`: strumento educativo (non consulenza finanziaria) che applica il metodo del corso
"Investire in azioni nel lungo termine" ai titoli USA e restituisce BUY / NO-BUY con un piano di
trade. Le interfacce sono due, CLI e web app locale, sullo stesso core. Serve perché a mano il
metodo è lento e gli screener non hanno tutti gli indicatori.

## A che punto siamo

- **Su `origin/main`, ultimo commit `bad7e92`, working tree pulito:**
  - CI verde su Python 3.11 e 3.13, più il job del frontend.
  - UI compilata dentro il pacchetto.
  - `CONTRIBUTING.md`, screenshot AAPL aggiornato nel README.
  - Due giri di audit Codex corretti.
  - Storico delle analisi in CSV, con pagina History.
- **Verifiche:**
  - `ruff check .` e `ruff format --check .` passano.
  - `pytest -m "not slow"`: 189 test.
  - In `web/`: `npm run lint` e `npm run build` passano.
  - Web app provata nel browser su un server di prova: PIN, History, modifica ed eliminazione,
    larghezza 375px.
- **Fatto per M7:** CI, `CONTRIBUTING.md`, screenshot, UI nel wheel. Il wheel si costruisce e
  contiene `ilovestock/static/`.
- **Non fatto:** pubblicazione su PyPI. Portfolio (fase 2) è ancora una pagina segnaposto.
- **Mai eseguito:** `pytest -m slow`, che interroga Finviz dal vivo.

## Cosa abbiamo provato che NON ha funzionato

- **Togliere 3.11 dalla matrice CI** (modifica non committata trovata a inizio sessione) non
  risolveva niente. La causa era `from tests.conftest import FIX`, che fallisce senza la root
  del repo in `sys.path`. Corretto con `pythonpath = ["."]` in `pyproject.toml`.
- **Heredoc Python lanciato dal tool Bash per modifiche con backslash:** il tool riduce `\\` a
  `\`, quindi `\n` nei test diventava un a capo vero e `\d` produceva un warning. Per testo con
  backslash usare Edit o Write, non script inline.
- **`pip wheel .` nel repo** lascia una cartella `build/` che ruff poi controlla. Ora `build/` e
  `dist/` sono in `.gitignore`. Costruire il wheel in una cartella esterna.
- **Screenshot SVG con la console di Rich forzata a terminale:** su Windows la pipe è cp1252 e
  lo spinner (`⠋`) fa crashare l'esecuzione, oppure finisce nell'immagine. Funziona così:
  `Console(record=True, file=io.StringIO(), color_system="truecolor")`.
- **Screenshot con il percorso reale dello storico:** nell'SVG pubblico finiva
  `C:\Users\zhouy\...`. Per l'immagine si sostituisce `history.append` con una funzione che non
  scrive e `HISTORY_PATH` con `~/.config/...`.
- **`session_end` scritto aspettandosi un epoch:** yfinance 1.7 restituisce
  `currentTradingPeriod.regular.end` come `Timestamp` già con timezone, e il fetch live del
  benchmark crashava. Ora gestisce entrambi i formati, con un test per ciascuno.
- **Server di prova avviato con lo script vecchio** (senza `history_path`): puntava allo storico
  reale. Fermato prima che scrivesse. Passare sempre tutti i percorsi a `create_app`.

## Problemi incontrati e come li abbiamo risolti

- **La CI su GitHub non partiva subito dopo il push** (ci ha messo minuti): non è un errore,
  basta aspettare. Per seguirla usare `gh api .../actions/runs?head_sha=...`.
- **Rich interpretava i dati come markup:** era già risolto il 20/10 con `escape`.
- **La cache del giorno in un formato vecchio:** dopo aver cambiato `Fundamentals` o i nomi dei
  file di cache, cancellare i file del giorno in `~/.cache/ilovestock`, altrimenti i campi nuovi
  restano vuoti.

## Decisioni prese

- **`--allow-missing`:** verdetto `BUY*` (dati incompleti), mai un BUY pieno. Scartati: un
  minimo di dati richiesti, oppure correggere solo la documentazione.
- **PIN:** si imposta solo nel terminale con `ilovestock serve`, mai via HTTP. Scartato un token
  monouso nel browser.
- **CORS:** rimosso. Il proxy di Vite è same-origin, e c'è un controllo `Origin` (403
  cross-origin).
- **D7, consolidamento e volume:** ora sono **bloccanti** (scelta dell'utente, come nel corso):
  correzione < 50% nelle 10 settimane, volume della settimana di breakout > media a 10
  settimane. Prima erano informativi.
- **Segnali settimanali** (forza relativa, Donchian) solo su settimane chiuse: il corso conferma
  il breakout sulla chiusura settimanale. Scartato il breakout a settimana in corso.
- **Attesa dopo la trimestrale:** almeno 1 sessione di reazione, 5 se la reazione muove il
  prezzo del 5% o più. È l'interpretazione di "1-5 giorni in base al movimento" detta
  dall'utente. La data viene dal campo `Earnings` di Finviz, quando è passata (BMO/AMC); senza
  BMO/AMC si assume AMC.
- **Crescita:** resta `yoy` come default (D2). Nel README è scritto che è una deviazione dal
  corso (che usa Q/Q).
- **`max_position_pct`:** massimo 10% come nel corso. Soglie di crescita e ROE >= 0, ownership
  istituzionale tra 0 e 100.
- **Storico:**
  - CSV in `~/.config/ilovestock/history.csv`, una riga per ticker per analisi.
  - Criteri e motivi salvati come JSON in una colonna, perché i nomi dei criteri cambiano.
  - I ticker con errore di dati non si salvano.
  - Scartato SQLite: l'utente ha chiesto un CSV.
- **Modifiche allo storico:** si possono cambiare nota, verdetto, prezzo, livelli e azioni; i
  criteri restano in sola lettura. Cambiare i dati aggiunge `edited_at`, la nota no.
- **Layout della pagina History:** A (timeline con "What changed"). Scartato B (matrice criteri
  × date).
- **Limite di ticker:** 50 per esecuzione, sia in CLI (`--max-tickers`) sia sul web.
- **Push:** `PROJECT.md` riga 9 dice di chiedere prima di ogni `git push`. In questa sessione
  l'utente ha pushato da sé gli ultimi commit.

## File toccati

- `pyproject.toml`: `pythonpath` di pytest, `package-data` `static/**/*`.
- `.gitignore`: `src/ilovestock/static/`, `build/`, `dist/`, `.superpowers/`.
- `web/vite.config.ts`: build in `../src/ilovestock/static`.
- `src/ilovestock/api/app.py`:
  - niente CORS; middleware `Origin` e limite di 64 KiB sul body;
  - endpoint `/api/pin/setup` rimosso;
  - lock sul controllo del PIN; pattern del PIN controllato prima dell'hash;
  - endpoint `/api/history` (GET, PATCH, DELETE).
- `src/ilovestock/cli.py`: `serve` chiede il PIN nel terminale; `--max-tickers`; scrittura
  nello storico dopo `analyze`.
- `src/ilovestock/history.py` (nuovo): CSV con append, lettura, modifica ed eliminazione, lock
  tra processi (`history.csv.lock`), riscrittura atomica.
- `src/ilovestock/models.py`:
  - `Verdict.BUY_INCOMPLETE`;
  - valore non finito → N/D;
  - `price` e `fundamentals_date` sul risultato;
  - `last_earnings`, `last_earnings_amc` e `fetched` su `Fundamentals`.
- `src/ilovestock/config.py`: valori finiti, fasce di market cap crescenti, `max_position_pct`
  <= 10, soglie >= 0.
- `src/ilovestock/indicators.py`: `drop_running_week` e `completed_weeks`.
- `src/ilovestock/rules/technical.py`: settimane chiuse; nuovi criteri `consolidation` e
  `breakout_volume`.
- `src/ilovestock/rules/earnings.py`: `post_earnings`.
- `src/ilovestock/rules/trade_plan.py`: `restart` sull'ultima settimana chiusa; scale-out legato
  al target; tolte le righe sul consolidamento.
- `src/ilovestock/rules/verdict.py`: `BUY*`.
- `src/ilovestock/analysis.py`: errori di analisi assegnati al singolo ticker; criterio
  post-earnings; prezzo e date.
- `src/ilovestock/providers/yahoo.py`: solo USD; scarto delle righe con NaN; `session_end`
  (chiusure anticipate).
- `src/ilovestock/providers/finviz.py`: anno della data earnings più vicina; data dell'ultima
  trimestrale; limite sullo screener.
- `src/ilovestock/providers/cache.py`: chiave per sessione di New York; scritture atomiche.
- `src/ilovestock/report.py`: stile di `BUY*`; date di prezzi e fondamentali.
- `src/ilovestock/inputs.py`: `MAX_TICKERS`.
- `web/src/`:
  - `pages/History.tsx` (nuovo);
  - `App.tsx` (route `#history/TICKER`), `Sidebar.tsx`, `api.ts`, `types.ts`;
  - `PinScreen.tsx` (solo sblocco);
  - `components.tsx`, `pages/Dashboard.tsx` e `pages/Analysis.tsx` (`BUY*`, date);
  - `pages/Settings.tsx` (suggerimento sul 10%).
- `tests/`: `test_history.py` (nuovo), più test in `test_api`, `test_cli`, `test_providers`,
  `test_rules` e `test_trade_plan`.
- `README.md`, `CONTRIBUTING.md` (nuovo), `PROJECT.md` (decisioni D1, D3, D7 e D11 chiuse),
  `docs/img/analyze-aapl.svg`.
- `docs/handoff/2026-10-20-cli-and-web-app.md`: marcato come superato.

## Dove vogliamo andare

1. Prepara la prima release su PyPI:
   - in `web/` lancia `npm ci && npm run build`;
   - lancia `python -m build` in una cartella pulita (installa `build` se manca);
   - controlla che il wheel contenga `ilovestock/static/index.html`;
   - installa il wheel in un venv nuovo e prova `ilovestock --help`, `ilovestock serve` (con un
     PIN di prova in una cartella temporanea) e un `analyze` offline o su un ticker, chiedendo
     prima.
2. Chiedi all'utente l'ok per caricare su PyPI. Servono il suo account e un token, che non vanno
   scritti nel repo. Valuta prima TestPyPI.
3. Dopo la release: Portfolio (fase 2: hold/sell, trailing stop, tetto per settore del 20%,
   pause dopo -10% o 7 perdite). Parti da un brainstorming con l'utente.

## Da sapere prima di toccare qualcosa

- **Comandi:** usare `.venv/Scripts/python`, `.venv/Scripts/ruff`, `.venv/Scripts/pytest`. Il
  venv è stato ricreato con Python 3.12 e `pip install -e ".[dev]"`.
- **Frontend:** `npm run build` scrive in `src/ilovestock/static/` (ignorata da git). Senza
  build, il server risponde "Frontend not built".
- **Server di prova:** non usare il PIN reale né lo storico reale. Usa
  `create_app(pin_path=..., config_path=..., history_path=...)` con una cartella temporanea e
  imposta il PIN con `PinStore(path).set("4821")` prima di avviare, perché via HTTP non si può
  più. Gli script di prova della sessione erano nello scratchpad e non esistono più.
- **Finviz dal vivo:** ogni nuova richiesta (analisi reali, fixture, `pytest -m slow`) va
  chiesta all'utente. I test di default restano offline.
- **Ogni analisi reale scrive nello storico** in `~/.config/ilovestock/history.csv`. Nei test,
  la fixture `offline` lo devia su `tmp_path`.
- **Cache in `~/.cache/ilovestock`:** i prezzi sono indicizzati per sessione (`AAAA-MM-GG` o
  `AAAA-MM-GG-open` prima delle 16:00 di New York), i fondamentali per giorno.
- **Hook GateGuard:** blocca `rm -rf` e la prima modifica di ogni file finché non si dichiarano i
  fatti richiesti (file coinvolti, rollback, istruzione dell'utente). È normale: dichiararli e
  riprovare.
- **Meno BUY:** con consolidamento, volume, settimane chiuse e attesa post-earnings ci sono meno
  BUY di prima. È voluto.
- **Lockout del PIN:** resta globale, e un processo locale ostile può tenerlo attivo. È un limite
  noto e documentato nel codice.
- **Directive:** non creare file in `directives/` senza chiedere (`AGENT.md`).
