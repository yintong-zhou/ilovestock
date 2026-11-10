Leggo il codice di `report()` e `ProgressOut` prima di scrivere la patch.

## Backend: piano per il build developer (Forge)

Ho letto `api/app.py:75-85, 176-199, 332-334` e `tests/test_api.py:320-368`. Il design è già approvato; qui fisso i dettagli di implementazione (L1). Non cambia nessun endpoint e il payload resta compatibile: i due campi sono nuovi e opzionali.

**Punto di attenzione.** `test_short_run_keeps_long_runs_progress` assegna a mano un `ProgressOut` nello slot e confronta `model_dump()` con la risposta. Il design sotto lo lascia passare senza toccarlo. Un `ProgressOut` senza informazioni di fase deve dare `eta_seconds=None` e `started_at=None`.

## Phase 1: `eta.py` puro con test
**Goal:** il calcolo della stima, senza clock e senza I/O.
- Nuovo `src/ilovestock/eta.py`:
  - `MIN_DONE = 2`.
  - `estimate_eta(phase_started, now, done, total) -> float | None`.
  - Restituisce `None` se `total <= 0`, se `done < MIN_DONE` o se `phase_started` è `None`.
  - Se `done >= total` restituisce `0.0`.
  - Altrimenti calcola `max(0.0, (now - phase_started) / done * (total - done))`.
  - Il modulo non importa `time`: `now` arriva dal chiamante.
- Nuovo `tests/test_eta.py` con valori numerici espliciti, senza `sleep` e senza rete:
  - `total=0`;
  - `done` 0 e 1;
  - metà run;
  - `done == total`;
  - `done > total` e `total < 0`: nessuna eccezione, risultato ≥ 0 o `None`;
  - `phase_started=None`;
  - `now < phase_started`: il risultato è 0.0, mai negativo.
- **Checks:** `pytest tests/test_eta.py`, `ruff check .`, `ruff format --check .`.

## Phase 2: payload e `report()` in `api/app.py`
**Goal:** esporre `started_at` ed `eta_seconds`, con lo stato per run.
- `ProgressOut` guadagna `started_at: float | None = None` ed `eta_seconds: float | None = None`.
- Aggiungere a `ProgressOut` un `PrivateAttr` `_phase: tuple[float, int] | None`, cioè `(monotonic di inizio fase, total)`. Non compare nel JSON.
- `create_app` accetta due parametri opzionali, `clock=time.monotonic` e `wall=time.time`, per i test.
- `report(kind)`:
  - all'inizio salva `started_at = wall()` e `phase = None`;
  - in `update`, se `total > 0` e (`phase is None` o `phase[1] != total`), imposta `phase = (clock(), total)`. Così la lettura iniziale dello screener e un cambio di `total` non entrano nella media;
  - con `total == 0` imposta `phase = None`;
  - crea `ProgressOut(text, done, total, started_at=started_at)`, copia `phase` in `_phase`, e assegna lo slot;
  - il `finally` con `if running[kind] is last` resta invariato.
- `GET /api/progress`: per ogni slot non vuoto restituisce `model_copy(update={"eta_seconds": estimate_eta(...)})`, calcolato con `clock()` al momento della richiesta. Se `_phase` è `None` l'ETA è `None`. Nessuna soglia nell'API: `MIN_DONE` sta in `eta.py`.
- **Checks:** `ruff check .`, `ruff format --check .`, `pytest -m "not slow"`.

## Phase 3: test API
**Goal:** coprire i nuovi campi senza indebolire i test esistenti.
- `test_progress_during_screen` e `test_short_run_keeps_long_runs_progress` restano invariati. Il secondo deve passare così com'è.
- Nuovi test in `tests/test_api.py`, con `make_client` che passa un `clock` e un `wall` finti:
  - `started_at` resta costante durante un run e cambia nel run successivo;
  - `eta_seconds` è `None` sotto 2 elementi e positivo dopo;
  - a `total=0` il valore è `None`, e la fase iniziale dello screener non entra nella media;
  - il salto del clock di sistema (`wall`) non cambia l'ETA;
  - un payload senza i nuovi campi si valida con i default `None`;
  - `/api/progress` senza sessione dà 401 (già coperto).
- Il `make_client` di test oggi non passa `clock`/`wall`: aggiungerli come parametri opzionali dell'helper.
- **Checks:** `pytest -m "not slow"` verde, e riportare l'output reale.

## Phase 4: frontend e CI (Gon e Orion)
**Goal:** la parte già approvata, che parte dal contratto sopra.
- `web/src/types.ts`: `started_at?: number | null` ed `eta_seconds?: number | null` in `Progress`.
- `vitest` come devDependency, `progressFormat.ts` con test, `JobProgress` con la riga 3, e `npm test` nel job `web` di `ci.yml` tra lint e build, come da brief.
- **Checks:** da `web/`, `npm ci`, `npm test`, `npm run lint`, `npm run build`. I `*.test.ts` non devono finire in `src/ilovestock/static/`.

Resta da fare il salvataggio del brief in `docs/handoff/progress-eta-brief.md`. Lo fa chi applica per primo la patch. Nessun push e nessuna chiamata live a Finviz o Yahoo.