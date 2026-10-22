# Screener dei fondamentali: piano di implementazione

> **Per gli agenti:** SUB-SKILL OBBLIGATORIA: usare superpowers:subagent-driven-development
> (consigliata) o superpowers:executing-plans per eseguire il piano task per task. I passi usano
> le checkbox (`- [ ]`) per il tracciamento.

**Obiettivo:** il comando `ilovestock screen` e la pagina Screener della web app. Applicano i
criteri fondamentali di `analyze` a tutte le azioni quotate negli USA e restituiscono i primi N
titoli ordinati per un punteggio di qualità (ROIC + variazione del margine operativo a un
anno). In più, `analyze` mostra una riga Quality informativa.

**Architettura:**
- Un modulo core `screener.py` fa tre cose: un pre-filtro largo con l'URL dello screener
  Finviz costruito dalla config, la verifica esatta di ogni candidato con la stessa funzione
  usata da `analyze` (`analysis.fundamental_checks`), e la classifica con `quality.py`.
- CLI e API sono strati sottili sopra il core. La web app aggiunge una pagina e precompila
  Analysis.

**Stack:** Python 3.11+, Typer/Rich, FastAPI, pandas, `finviz` 2.0.0, yfinance 1.7.0, React +
Vite + Tailwind. Nessuna dipendenza nuova.

**Spec:** [docs/superpowers/specs/2026-10-22-fundamental-screener-design.md](../specs/2026-10-22-fundamental-screener-design.md)

## Vincoli globali

- Il core è unico per CLI e web, e `cli.py` non contiene regole.
- Nessuna rete nei test di default né in CI: si usano fixture registrate.
- Le chiavi dei campi Finviz e i codici dei filtri si prendono da risposte reali.
- **Ogni richiesta dal vivo a Finviz va chiesta prima all'utente.**
- Il dato mancante resta `N/D` e non diventa mai PASS. Nello screener N/D non passa.
- Un titolo dato "tutti pass" dallo screener non deve mai essere bocciato da `analyze`, lo
  stesso giorno e con la stessa config, su un criterio fondamentale o di trimestrale.
- Il punteggio di qualità non tocca il verdetto, la matrice delle regole, i motivi di NO-BUY né
  i criteri salvati nello storico.
- `--max` va da 1 a 50 (`inputs.MAX_TICKERS`), con default 20. Il tetto dei candidati è
  `MAX_CANDIDATES = 100`.
- L'universo è NASDAQ, NYSE e AMEX, senza il filtro `geo_usa`.
- `post_earnings` resta fuori dal filtro dello screener.
- Prove manuali: PIN, config e storico sempre in una cartella temporanea
  (`create_app(pin_path=..., config_path=..., history_path=...)`).
- Testo del terminale solo ASCII, compresa la colonna "Op. margin chg (1y)". Su Windows la
  pipe è cp1252 e `Δ` diventa `�`. La web app può usare `Δ`.
- Le etichette della UI sono in inglese.
- Comandi di verifica:
  - `.venv/Scripts/ruff.exe check .`
  - `.venv/Scripts/ruff.exe format --check .`
  - `.venv/Scripts/pytest.exe -m "not slow" -q`
  - in `web/`: `npm run lint` e `npm run build`

## Punti da controllare in revisione

1. **Cache del giorno nel vecchio formato**, cioè un JSON senza `roic_pct` né
   `operating_income`. Deve caricarsi senza errori e dare una Quality N/D, non rompere lo
   screener. Test nel Task 1.
2. **`--max` più grande del numero di titoli che passano.** Si mostrano tutti quelli che
   passano, e i conteggi lo dicono ("showing 3"). Test nel Task 5.
3. **Variazione di margine negativa o assente.** Va scritta `-0.5 pt` o `N/D`, mai `+-0.5` o
   `None`. Test nel Task 3.
4. **Zero titoli che passano.** Il terminale esce con codice 0 e non salva il file. Il web
   nasconde i pulsanti. Test nel Task 6, controllo manuale nel Task 8.
5. **Un titolo subito dopo la trimestrale** (`last_earnings` ieri) passa comunque lo screener:
   `post_earnings` non è un filtro. Test nel Task 5.

---

### Task 1: dati ROIC e utile operativo

**File:**
- Modifica: `src/ilovestock/models.py` (`Fundamentals`)
- Modifica: `src/ilovestock/providers/finviz.py` (`KEYS`)
- Modifica: `src/ilovestock/providers/yahoo.py` (`YahooProvider.fundamentals`)
- Test: `tests/test_providers.py`

**Interfacce:**
- Produce i campi `Fundamentals.roic_pct: float | None = None` (Finviz `"ROIC"`) e
  `Fundamentals.operating_income: list[float | None] = field(default_factory=list)` (Yahoo
  trimestrale, dal più recente).

- [ ] **Passo 1: test che falliscono**

```python
def test_parse_snapshot_roic():
    data = json.loads((FIX / "AAPL_finviz.json").read_text())
    assert finviz.parse_snapshot(data, date(2026, 10, 22))["roic_pct"] == 72.08

def test_yahoo_operating_income(fake_yf):
    f = YahooProvider().fundamentals("HZO")
    assert f.operating_income[0] == 37219000.0 and f.operating_income[4] == 27515000.0

def test_cache_loads_old_format_without_new_fields(tmp_path):
    # JSON della cache scritto prima di questo task: mancano roic_pct e operating_income
    old = {"sales": [1.0], "eps": [1.0], "roe_pct": 20.0, "market_cap": 1e9, "next_earnings": None}
    (tmp_path / f"{date.today():%Y-%m-%d}_OLD_fundamentals.json").write_text(json.dumps(old))
    f = CachedProvider(inner=None, cache_dir=tmp_path).fundamentals("OLD")
    assert f.roic_pct is None and f.operating_income == []
```

- [ ] **Passo 2:** `.venv/Scripts/pytest.exe tests/test_providers.py -q -k "roic or operating or old_format"`. Atteso: FAIL (`KeyError` / `AttributeError`).
- [ ] **Passo 3: implementazione.**
  - Aggiungi i due campi in fondo a `Fundamentals`, con default, così la cache vecchia si
    carica ancora.
  - In `KEYS`: `"roic_pct": "ROIC",  # "72.08%"`.
  - In `YahooProvider.fundamentals`: `operating_income=_row(stmt, "Operating Income")`.
- [ ] **Passo 4:** stesso comando, atteso PASS. Poi tutta la suite `-m "not slow"`.
- [ ] **Passo 5: commit** `git commit -m "Add ROIC and quarterly operating income to fundamentals"`

---

### Task 2: calcolo di qualità e punteggio

**File:**
- Modifica: `src/ilovestock/models.py` (nuovo dataclass `Quality`)
- Crea: `src/ilovestock/quality.py`
- Test: `tests/test_quality.py`

**Interfacce:**
- Consuma `Fundamentals.roic_pct`, `.sales` e `.operating_income` (Task 1).
- Produce:
  - in `models.py`: `@dataclass class Quality: roic_pct: float | None; margin_pct: float | None; margin_year_ago_pct: float | None; margin_change_pt: float | None`
  - in `quality.py`:
    - `margin_change(sales: list[float | None], operating_income: list[float | None]) -> tuple[float | None, float | None, float | None]` restituisce (margine ultimo trimestre %, margine dello stesso trimestre un anno prima %, differenza in punti). Usa gli indici 0 e 4. Tutto `None` se mancano 5 trimestri, se un valore è `None` o se il fatturato è <= 0.
    - `quality(f: Fundamentals) -> Quality`
    - `ranks(values: list[float | None]) -> list[int | None]`: classifica a competizione, dove 1 è il valore più alto, i pari merito hanno la stessa posizione e `None` resta `None`.
    - `scores(items: list[Quality]) -> list[float]`: per ogni misura il percentile è `100 * (n - rank) / (n - 1)`. Con `n == 1` vale 100, con rank `None` vale 0. Il punteggio è la media dei percentili di ROIC e variazione del margine, arrotondata a 1 decimale.

- [ ] **Passo 1: test che falliscono**

```python
def test_margin_change_same_quarter_last_year():
    sales = [200.0, 150.0, 140.0, 130.0, 100.0]
    op = [30.0, 15.0, 14.0, 13.0, 10.0]
    assert margin_change(sales, op) == (15.0, 10.0, 5.0)

@pytest.mark.parametrize("sales,op", [
    ([200.0, 1, 1, 1], [30.0, 1, 1, 1]),                      # 4 trimestri
    ([200.0, 1, 1, 1, 0.0], [30.0, 1, 1, 1, 10.0]),           # fatturato 0
    ([200.0, 1, 1, 1, 100.0], [None, 1, 1, 1, 10.0]),         # dato mancante
])
def test_margin_change_nd(sales, op):
    assert margin_change(sales, op) == (None, None, None)

def test_ranks_ties_and_none():
    assert ranks([10.0, None, 10.0, 5.0]) == [1, None, 1, 3]

def test_scores_scale_and_average():
    q = lambda roic, chg: Quality(roic, None, None, chg)
    assert scores([q(30, 3), q(20, 1), q(10, 2)]) == [100.0, 25.0, 25.0]

def test_scores_none_is_worst_and_single_is_100():
    q = lambda roic, chg: Quality(roic, None, None, chg)
    assert scores([q(None, 1), q(10, None)]) == [50.0, 50.0]
    assert scores([q(5, 1)]) == [100.0]
```

- [ ] **Passo 2:** `.venv/Scripts/pytest.exe tests/test_quality.py -q`. Atteso: FAIL (import).
- [ ] **Passo 3:** implementa le funzioni con le firme sopra. I margini e la differenza vanno
  arrotondati a 2 decimali.
- [ ] **Passo 4:** stesso comando, atteso PASS.
- [ ] **Passo 5: commit** `git commit -m "Quality: ROIC and operating margin change, rank-based score"`

---

### Task 3: giudizio condiviso e riga Quality in `analyze` (terminale)

**File:**
- Modifica: `src/ilovestock/analysis.py`
- Modifica: `src/ilovestock/models.py` (`TickerAnalysis.quality`)
- Modifica: `src/ilovestock/report.py`
- Test: `tests/test_rules.py`, `tests/test_quality.py`, `tests/test_cli.py`, `tests/test_api.py`

**Interfacce:**
- Consuma `quality.quality` (Task 2).
- Produce:
  - in `analysis.py`: `fundamental_checks(fund: Fundamentals, daily: pd.DataFrame, cfg: Config, today: date) -> tuple[list[CriterionResult], CriterionResult]`, cioè `(fundamental(...), earnings(...))`. Docstring: "same judgment for analyze and screen". `analyze()` la usa al posto delle due chiamate dirette.
  - `TickerAnalysis.quality: Quality | None = None`, valorizzato da `analyze()` nel ramo di successo.
  - in `report.py`: `quality_text(q: Quality) -> str`, per esempio `"ROIC 31.2%, op. margin +4.1 pt"`. Le parti mancanti diventano `"ROIC N/D"` e `"op. margin N/D"`. Formati: ROIC `{:.1f}%`, differenza `{:+.1f} pt`.
- `detail()` aggiunge alla tabella Fundamental l'ultima riga `Quality | quality_text | - | [cyan]INFO[/] | informative, does not change the verdict`.
- `history.py` ed `export.py` non cambiano. L'export JSON avrà `quality` da solo, tramite
  `asdict`, e va bene così.

- [ ] **Passo 1: test che falliscono**

```python
# tests/test_rules.py
def test_fundamental_checks_is_what_analyze_uses(fake_yf, fake_finviz, bench_close):
    p = FinvizProvider(YahooProvider())
    r = analyze("HZO", p, bench_close, CFG, date(2026, 10, 22))
    fund, earn = fundamental_checks(p.fundamentals("HZO"), p.history("HZO"), CFG, date(2026, 10, 22))
    assert r.fundamental == fund and r.earnings == earn
    assert r.quality.roic_pct == 0.28

# tests/test_quality.py
def test_quality_text_signs_and_nd():
    assert quality_text(Quality(31.2, 18.1, 14.0, 4.1)) == "ROIC 31.2%, op. margin +4.1 pt"
    assert quality_text(Quality(5.0, 1.0, 1.5, -0.5)) == "ROIC 5.0%, op. margin -0.5 pt"
    assert quality_text(Quality(None, None, None, None)) == "ROIC N/D, op. margin N/D"

# tests/test_cli.py
def test_detail_shows_quality_row(offline):
    result = runner.invoke(cli.app, ["analyze", "HZO", "--detail"])
    assert result.exit_code == 0 and "Quality" in result.output and "INFO" in result.output

# tests/test_api.py: nel test esistente che analizza HZO (se non c'è, in uno nuovo
# sbloccato con unlocked(client)) aggiungere
#     assert body["results"][0]["quality"]["roic_pct"] == 0.28
```

- [ ] **Passo 2:** `.venv/Scripts/pytest.exe -m "not slow" -q -k "fundamental_checks or quality_text or quality_row or analyze"`. Atteso: i nuovi FAIL.
- [ ] **Passo 3:** implementa come descritto nelle interfacce.
- [ ] **Passo 4:** tutta la suite `-m "not slow"`, atteso PASS. I test sul verdetto e sullo
  storico non devono cambiare.
- [ ] **Passo 5: commit** `git commit -m "Shared fundamental checks; informative Quality row in analyze"`

---

### Task 4: URL dello screener Finviz e contratto sui filtri

**File:**
- Crea: `src/ilovestock/screener.py` (solo la parte URL in questo task)
- Modifica: `src/ilovestock/providers/finviz.py` (`TooManyResults`)
- Modifica: `execution/record_fixtures.py` (modalità `--screen`)
- Crea: `tests/fixtures/finviz_screener_default.html`, **registrata dal vivo dopo il sì
  dell'utente**
- Test: `tests/test_screener.py`, `tests/test_providers.py`

**Interfacce:**
- Produce:
  - in `finviz.py`: `class TooManyResults(FinvizError)` con `__init__(self, message: str, total: int)` e l'attributo `total`. La lancia `screener_tickers` al posto dell'attuale `FinvizError` "screener has N results". Il messaggio resta uguale, così i test esistenti passano.
  - in `screener.py`: `MAX_CANDIDATES = 100`, `DEFAULT_RESULTS = 20`, `MAX_RESULTS = inputs.MAX_TICKERS`.
  - `finviz_filters(cfg: Config) -> list[str]`, nell'ordine sales, eps, roe, instown, insttrans, div, cap.
  - `screener_url(cfg: Config) -> str`, cioè `"https://finviz.com/screener.ashx?v=111&f=" + ",".join(filters)`.
- Regola degli scaglioni: lo scaglione più largo che non scarta titoli validi. Le soglie
  candidate vanno verificate sulla fixture (passo 5):
  - `fa_salesqoq_o{5,10,15,20,25,30}` e `fa_epsqoq_o{...}`: il livello più alto <= minimo. Nessun filtro se il minimo è < 5 o se `growth_basis == "qoq"`.
  - `fa_roe_o{5,10,...,50}`: il livello più alto <= `roe_min`. Nessun filtro se è < 5.
  - `sh_instown_u{10,20,...,90}`: il livello più basso >= `institutional_own_max`. Nessun filtro se è > 90.
  - sempre `sh_insttrans_pos` e `fa_div_none`.
  - `cap_{microover,smallover,midover,largeover}` (50/300/2000/10000 milioni): il livello più alto <= `nano_max`. Nessun filtro se `nano_max` < 50.

- [ ] **Passo 1: test che falliscono (senza rete)**

```python
DEFAULT = load(Path("does-not-exist.toml"))

def test_filters_default_config():
    assert finviz_filters(DEFAULT) == [
        "fa_salesqoq_o20", "fa_epsqoq_o15", "fa_roe_o15", "sh_instown_u80",
        "sh_insttrans_pos", "fa_div_none", "cap_microover",
    ]

def test_filters_take_the_loosest_bucket():
    cfg = replace(DEFAULT, sales_growth_min=22, eps_growth_min=12, roe_min=3, institutional_own_max=85)
    f = finviz_filters(cfg)
    assert "fa_salesqoq_o20" in f and "fa_epsqoq_o10" in f and "sh_instown_u90" in f
    assert not any(x.startswith("fa_roe") for x in f)
    assert not any(x.startswith("sh_instown") for x in finviz_filters(replace(DEFAULT, institutional_own_max=95)))

def test_filters_qoq_leaves_growth_out():
    f = finviz_filters(replace(DEFAULT, growth_basis="qoq"))
    assert not any(x.startswith(("fa_salesqoq", "fa_epsqoq")) for x in f)

def test_screener_url_has_no_country_filter():
    assert "geo_" not in screener_url(DEFAULT)
```

In `tests/test_providers.py`, nel test esistente `test_screener_too_large_stops_after_first_page`:
`pytest.raises(finviz.TooManyResults)` e `assert exc.value.total == 261`.

- [ ] **Passo 2:** `.venv/Scripts/pytest.exe tests/test_screener.py tests/test_providers.py -q`. Atteso: FAIL.
- [ ] **Passo 3:** implementa le funzioni e `TooManyResults`. In `record_fixtures.py` aggiungi
  `record_screen()`, lanciata con `python execution/record_fixtures.py --screen`: costruisce
  `screener_url` dalla config di default e salva solo la prima pagina
  (`params={"r": 1}`) in `tests/fixtures/finviz_screener_default.html`. Le fixture
  `finviz_screener_p1/p2.html` restano come sono.
- [ ] **Passo 4:** test del passo 1 in PASS.
- [ ] **Passo 5: STOP, chiedere all'utente il permesso per una richiesta dal vivo a Finviz.**
  Dopo il sì: `.venv/Scripts/python.exe execution/record_fixtures.py --screen`. Riferisci
  all'utente il totale dei candidati stampato nella pagina (`#1 / N Total`).
- [ ] **Passo 6: test di contratto sulla fixture**

```python
def applied_filters(html: str) -> set[str]:
    m = re.search(r'screener-split-applied-filters"><span> <b>Filters:</b> (.*?)</span>', html)
    return set(m.group(1).replace("<!-- -->", " ").split())

def test_finviz_accepts_every_generated_filter():
    html = (FIX / "finviz_screener_default.html").read_text(encoding="utf-8")
    shown = {code.rsplit("_", 1)[0] + ":" + code.rsplit("_", 1)[1] for code in finviz_filters(DEFAULT)}
    assert shown <= applied_filters(html)  # Finviz ignores unknown codes: a missing one = wrong code
```

  Se un codice manca da `applied_filters`, il codice è sbagliato. Correggi la tabella degli
  scaglioni prendendo il valore dalla pagina reale e registra di nuovo, chiedendo ancora il
  permesso. Non indovinare.
- [ ] **Passo 7: commit** `git commit -m "Finviz screener URL from config thresholds, with contract fixture"`

---

### Task 5: core dello screener

**File:**
- Modifica: `src/ilovestock/screener.py`
- Test: `tests/test_screener.py`

**Interfacce:**
- Consuma:
  - `analysis.fundamental_checks` (Task 3)
  - `quality.quality`, `quality.ranks` e `quality.scores` (Task 2)
  - `finviz.screener_tickers` e `TooManyResults`, e `screener_url` (Task 4)
- Produce:
  - `@dataclass ScreenHit: ticker: str; market_cap: str | None; quality: Quality; score: float; roic_rank: int | None; margin_rank: int | None`
  - `@dataclass ScreenResult: candidates: int; passed: int; errors: list[str]; hits: list[ScreenHit]`
  - `screen(provider: MarketDataProvider, cfg: Config, today: date, max_results: int = DEFAULT_RESULTS, progress: Callable[[str], None] | None = None) -> ScreenResult`
- Comportamento:
  1. `finviz.screener_tickers(screener_url(cfg), MAX_CANDIDATES)`. La funzione va cercata
     tramite il modulo al momento della chiamata, perché i test la sostituiscono.
  2. Su `TooManyResults` lancia `FinvizError(f"{e.total} candidates from Finviz: max {MAX_CANDIDATES}. Tighten the fundamental thresholds in the config")`.
     Con `qoq` il messaggio aggiunge `'; growth_basis = "yoy" also filters growth on Finviz'`.
     Le altre `FinvizError`, compreso "no tickers found", passano così come sono.
  3. Per ogni candidato chiama `progress(t)`, poi `history`, `fundamentals` e
     `fundamental_checks`. Passa solo se tutti gli stati sono PASS. Un'eccezione su un ticker
     lo aggiunge a `errors` e la ricerca continua.
  4. `market_cap` è il `value` del criterio "Market cap".
  5. Punteggi e posizioni si calcolano su tutti i titoli che passano. L'ordine è punteggio
     decrescente, poi ROIC decrescente (`None` in fondo), poi ticker. Si tengono i primi
     `max_results`.

- [ ] **Passo 1: test che falliscono.**
  - Importa `good_fundamentals` e `prices` da `tests.test_rules`: `pytest` ha
    `pythonpath = ["."]`. Con i default passano tutti e 7 i criteri, e `next_earnings` cade il
    2026-12-01.
  - `TODAY = date(2026, 10, 22)`.
  - Usa questo provider finto (`history` restituisce `prices()`):

```python
class FakeProvider:
    def __init__(self, data: dict[str, Fundamentals | Exception]): self.data = data
    def _get(self, t):
        v = self.data[t]
        if isinstance(v, Exception): raise v
        return v
    def history(self, t): self._get(t); return prices()
    def fundamentals(self, t): return self._get(t)

def run(monkeypatch, data, **kw):
    monkeypatch.setattr(finviz, "screener_tickers", lambda url, limit=None: list(data))
    return screen(FakeProvider(data), kw.pop("cfg", CFG), TODAY, **kw)

def test_screen_keeps_only_all_pass_and_counts(monkeypatch):
    r = run(monkeypatch, {"A": good_fundamentals(roic_pct=20.0), "B": good_fundamentals(roe_pct=10.0), "C": DataError("x")})
    assert (r.candidates, r.passed, r.errors, [h.ticker for h in r.hits]) == (3, 1, ["C"], ["A"])

def test_screen_nd_never_passes(monkeypatch):
    assert run(monkeypatch, {"A": good_fundamentals(inst_own_pct=None)}).passed == 0

def test_screen_ranks_and_cuts(monkeypatch):
    # operating_income vuoto per tutti: margine N/D, conta solo il ROIC
    data = {t: good_fundamentals(roic_pct=v) for t, v in (("A", 30.0), ("B", 10.0), ("C", 20.0))}
    r = run(monkeypatch, data, max_results=2)
    assert r.passed == 3 and [h.ticker for h in r.hits] == ["A", "C"]
    assert (r.hits[0].roic_rank, r.hits[0].margin_rank) == (1, None)

def test_screen_max_above_passed_shows_all(monkeypatch):
    data = {t: good_fundamentals() for t in ("A", "B", "C")}
    assert len(run(monkeypatch, data, max_results=20).hits) == 3

def test_screen_ignores_post_earnings(monkeypatch):
    f = good_fundamentals(last_earnings=TODAY - timedelta(days=1), last_earnings_amc=True)
    assert run(monkeypatch, {"A": f}).passed == 1

def test_screen_too_many_candidates(monkeypatch):
    def boom(url, limit=None): raise finviz.TooManyResults("x", total=150)
    monkeypatch.setattr(finviz, "screener_tickers", boom)
    with pytest.raises(finviz.FinvizError, match="150 candidates from Finviz: max 100"):
        screen(FakeProvider({}), CFG, TODAY)
    with pytest.raises(finviz.FinvizError, match="yoy"):
        screen(FakeProvider({}), replace(CFG, growth_basis="qoq"), TODAY)
```

  Lo stesso giudizio di `analyze` è garantito dalla struttura: entrambi chiamano
  `fundamental_checks`, e il Task 3 verifica che `analyze` la usi. Qui non serve un test in più.

- [ ] **Passo 2:** `.venv/Scripts/pytest.exe tests/test_screener.py -q`. Atteso: FAIL.
- [ ] **Passo 3:** implementa `screen` e i due dataclass.
- [ ] **Passo 4:** tutta la suite `-m "not slow"`, atteso PASS.
- [ ] **Passo 5: commit** `git commit -m "Screener core: exact fundamental check and quality ranking"`

---

### Task 6: comando `ilovestock screen`

**File:**
- Modifica: `src/ilovestock/cli.py`
- Modifica: `src/ilovestock/report.py` (`screen_table`)
- Modifica: `README.md` (sezione Usage), `PROJECT.md` (blocco `## CLI`)
- Test: `tests/test_cli.py`

**Interfacce:**
- Consuma `screener.screen`, `ScreenResult` e le costanti (Task 5), più `report.quality_text`
  (Task 3).
- Produce:
  - il comando `screen`, nello stile `Annotated` di `analyze`:
    - `max_results: Annotated[int, typer.Option("--max", min=1, max=screener.MAX_RESULTS, help="Max stocks in the list")] = screener.DEFAULT_RESULTS`
    - `out: Annotated[Path | None, typer.Option(help="Watchlist file")] = None`
    - `config_file: Annotated[Path | None, typer.Option("--config", help="Config file")] = None`
  - La docstring (l'help del comando) dice: "Find US-listed stocks that pass every fundamental rule, ranked by quality (ROIC and operating margin change). Only stocks with complete Finviz data are searched."
  - in `report.py`: `screen_table(result: ScreenResult) -> Table` con le colonne `#`, `Ticker`, `Market cap`, `ROIC`, `Op. margin chg (1y)`, `Score` e `Ranks`, dove `Ranks` è `"ROIC #2, margin #3 of 47"` e la posizione mancante è `N/D`.
- Testo fisso, in ordine:
  - `[dim]{finviz.WARNING}[/]` e `[dim]Only stocks with complete Finviz data are searched.[/]`
  - durante la ricerca: `console.status` con `Checking {t}...`
  - `{candidates} candidates from Finviz, {passed} pass every fundamental rule, showing {len(hits)} by quality score`
  - se ci sono errori: `[dim]Skipped for data errors: A, B[/]`
  - se `passed == 0`: `No stock passes every fundamental rule.`, nessun file, codice 0
  - altrimenti: la tabella, poi il file `out or Path("reports") / f"screen-{today:%Y-%m-%d}.txt"`. La prima riga è `# ilovestock screen {today}: top {n} of {passed} by quality score. Not financial advice.`, poi un ticker per riga. Si crea la cartella se non c'è.
  - `Watchlist saved: {path}` e `Next: ilovestock analyze --watchlist {path}`
  - il disclaimer, come in `print_report`
- Errori: `ConfigError` e `FinvizError` passano per `_fail(...)` con codice 1; qualsiasi altra
  eccezione del pre-filtro dà `_fail(f"Finviz screener failed: {e}")`.
- Il comando chiama `screener.screen(...)` tramite il modulo, perché i test lo sostituiscono.

- [ ] **Passo 1: test che falliscono**

```python
def test_screen_none_pass_exits_zero_without_file(offline):
    # offline: screener_tickers -> ["SCRN", "HZO"]; SCRN senza dati, HZO boccia (ROE 0.42%)
    result = runner.invoke(cli.app, ["screen", "--out", str(offline / "w.txt")])
    assert result.exit_code == 0, result.output
    assert "No stock passes" in result.output and not (offline / "w.txt").exists()
    assert "Skipped for data errors: SCRN" in result.output

def test_screen_saves_watchlist(offline, monkeypatch):
    hits = [ScreenHit("ABCD", "1,240M (small)", Quality(31.2, 18.1, 14.0, 4.1), 96.0, 2, 3),
            ScreenHit("EFGH", "640M (small)", Quality(22.8, 9.0, 2.7, 6.3), 93.0, 4, 1)]
    monkeypatch.setattr(cli.screener, "screen", lambda *a, **k: ScreenResult(47, 47, [], hits))
    out = offline / "w.txt"
    result = runner.invoke(cli.app, ["screen", "--max", "2", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert inputs.read_watchlist(out) == ["ABCD", "EFGH"]
    assert f"ilovestock analyze --watchlist {out}" in result.output.replace("\n", "")
    assert "ROIC #2, margin #3 of 47" in result.output

def test_screen_max_is_bounded():
    assert runner.invoke(cli.app, ["screen", "--max", "51"]).exit_code == 2
```

- [ ] **Passo 2:** `.venv/Scripts/pytest.exe tests/test_cli.py -q -k screen`. Atteso: FAIL.
- [ ] **Passo 3:** implementa il comando e `screen_table`. Nel README aggiungi la sezione
  "Find candidates (fundamentals first)": comando, opzioni, cosa misura il punteggio di
  qualità, avviso "only stocks with complete Finviz data", file prodotto e passo successivo con
  `analyze`. Nel blocco CLI di `PROJECT.md` aggiungi la riga
  `ilovestock screen [--max N] [--out FILE]`.
- [ ] **Passo 4:** tutta la suite `-m "not slow"`, ruff check e ruff format in PASS.
- [ ] **Passo 5: commit** `git commit -m "CLI: ilovestock screen with watchlist output"`

---

### Task 7: endpoint `POST /api/screen`

**File:**
- Modifica: `src/ilovestock/api/app.py`
- Test: `tests/test_api.py`

**Interfacce:**
- Consuma `screener.screen`, `ScreenHit` e `MAX_RESULTS` (Task 5).
- Produce:
  - `class ScreenIn(BaseModel): max: int = Field(screener.DEFAULT_RESULTS, ge=1, le=screener.MAX_RESULTS)`
  - `class ScreenOut(BaseModel): disclaimer: str; finviz_warning: str; screened_on: str; candidates: int; passed: int; errors: list[str]; hits: list[ScreenHit]`
  - la route `@app.post("/api/screen", dependencies=[Depends(session)])`
- Errori:
  - `ConfigError` e `FinvizError` danno 422 con il messaggio;
  - qualsiasi altra eccezione dà 502 `f"Finviz screener not available: {e}"`.
- Non scrive nello storico. Usa lo stesso `provider` di `/api/analyze` e chiama
  `screener.screen(...)` tramite il modulo.

- [ ] **Passo 1: test che falliscono**

```python
def test_screen_needs_session(client):
    assert client.post("/api/screen", json={"max": 20}).status_code == 401

def test_screen_bounds(client):
    unlocked(client)
    assert client.post("/api/screen", json={"max": 51}).status_code == 422

def test_screen_returns_hits_and_no_history(client, monkeypatch, tmp_path):
    unlocked(client)
    monkeypatch.setattr("ilovestock.providers.finviz.screener_tickers", lambda url, limit=None: ["HZO"])
    body = client.post("/api/screen", json={"max": 20}).json()
    assert (body["candidates"], body["passed"], body["hits"]) == (1, 0, [])
    assert not (tmp_path / "history.csv").exists()

def test_screen_too_many_is_422(client, monkeypatch):
    unlocked(client)
    def boom(url, limit=None): raise finviz.TooManyResults("x", total=150)
    monkeypatch.setattr("ilovestock.providers.finviz.screener_tickers", boom)
    r = client.post("/api/screen", json={})
    assert r.status_code == 422 and "150 candidates" in r.json()["detail"]
```

- [ ] **Passo 2:** `.venv/Scripts/pytest.exe tests/test_api.py -q -k screen`. Atteso: FAIL.
- [ ] **Passo 3:** implementa la route.
- [ ] **Passo 4:** tutta la suite `-m "not slow"` in PASS.
- [ ] **Passo 5: commit** `git commit -m "API: POST /api/screen"`

---

### Task 8: pagina Screener e riga Quality nella web app

**File:**
- Modifica: `web/src/types.ts`, `web/src/api.ts`, `web/src/format.ts`
- Modifica: `web/src/Sidebar.tsx`, `web/src/App.tsx`
- Modifica: `web/src/components.tsx` (`CriteriaTable`), `web/src/pages/Analysis.tsx`
- Crea: `web/src/pages/Screener.tsx`
- Modifica: `README.md` (una riga sulla pagina Screener, nella parte sulla web app)

**Interfacce:**
- Consuma `POST /api/screen` (Task 7) e `TickerAnalysis.quality` (Task 3).
- Produce:
  - in `types.ts`: `Quality`, `ScreenHit` e `ScreenOut`, che rispecchiano i dataclass Python; in più `TickerAnalysis.quality: Quality | null`.
  - in `api.ts`: `screen: (max: number) => request<ScreenOut>('POST', '/api/screen', { max })`.
  - in `format.ts`: `qualityText(q: Quality): string`, con lo stesso testo di `report.quality_text`.
  - `Page` acquista `'screener'`. La voce NAV "Screener" va prima di "Analysis", con un'icona a imbuto `<path d="M3 4h18l-7 8v6l-4 2v-8z" />`. Va aggiunta anche a `PAGES` in `App.tsx`.
  - In `App`, lo stato `lastScreen: ScreenOut | null` si azzera in `lock()`, come `lastRun`.
  - La prop `Analysis({ initialTickers }: { initialTickers: string, ... })` vale `useState(initialTickers.replaceAll(',', ' '))`. `App` passa `arg` quando `page === 'analysis'`.
  - `CriteriaTable` acquista la prop opzionale `quality?: Quality | null`. Se c'è, aggiunge
    l'ultima riga: `Quality`, `qualityText(q)`, `—`, `INFO` in `text-teal-tint`, nota
    `Informative, does not change the verdict`. La passa solo la tabella Fundamental di
    `Analysis`.
- Pagina `Screener.tsx` (in inglese, stile di `Analysis.tsx`, bozza approvata nello spec):
  - `PageHeader` "Screener", con il testo "Finds US-listed stocks that pass every fundamental rule, ranked by quality."
  - Form:
    - `Field` "Max results" con input numerico (min 1, max 50, default 20);
    - pulsante "Search", disattivato mentre gira;
    - mentre gira: `Message kind="info"` "Checking each candidate takes a few seconds (up to 100 candidates).".
  - Risultati:
    - la riga di conteggio `{passed} stocks pass every fundamental rule · showing the top {hits.length} by quality score`;
    - la tabella con #, Ticker (riga che si apre come in Analysis), Market cap, ROIC, Op. margin Δ (1y) e Quality score (intero);
    - la nota della riga aperta: `ROIC x% → #r of n · Operating margin a% → b% vs the same quarter last year (±c pt) → #r of n · Score = average of the two ranks, 0–100 (100 = best of the n)`.
  - Se ci sono titoli:
    - "Analyze these {n}" imposta `window.location.hash = '#analysis/' + encodeURIComponent(tickers.join(','))`;
    - "Save as watchlist" scarica un Blob `screen-YYYY-MM-DD.txt`, con lo stesso contenuto del file della CLI.
  - Se non ce ne sono: `Message` "No stock passes every fundamental rule." e nessun pulsante.
  - Gli errori vanno in un `Message kind="info"` "Skipped for data errors: …".
  - Footer: disclaimer, `finviz_warning` e "Only stocks with complete Finviz data are searched."
  - Gli errori dell'API passano per `onApiError`, come le altre pagine.

- [ ] **Passo 1:** implementa tipi, API, formattazione, sidebar, route, prefill di Analysis e
  riga Quality.
- [ ] **Passo 2:** implementa `Screener.tsx`.
- [ ] **Passo 3:** in `web/` lancia `npm run lint` e `npm run build`. Atteso: nessun errore, la
  build scrive in `src/ilovestock/static/`.
- [ ] **Passo 4: controllo nel browser** su un server di prova. Usa `create_app` con PIN,
  config e storico in una cartella temporanea e `PinStore(path).set(...)`. Sostituisci
  `ilovestock.screener.screen` con un `ScreenResult` finto di 3 titoli, così non serve la rete.
  Controlla:
  - sidebar e route `#screener`;
  - la riga che si apre con la nota;
  - "Analyze these 3", che porta su Analysis con i tickers compilati e l'analisi non partita;
  - il download della watchlist;
  - il caso con zero titoli, senza pulsanti;
  - la larghezza di 375px senza scroll orizzontale;
  - la riga Quality nel dettaglio di Analysis.
- [ ] **Passo 5: commit** `git commit -m "Web: Screener page and Quality row"`

---

### Task 9: verifica finale

- [ ] **Passo 1:** `ruff check .`, `ruff format --check .`, `pytest -m "not slow"`; in `web/`
  `npm run lint` e `npm run build`. Tutto deve passare.
- [ ] **Passo 2: STOP, chiedere all'utente il permesso** per una ricerca reale
  (`ilovestock screen`, fino a 100 candidati con Finviz e Yahoo dal vivo). Va lanciata con
  `USERPROFILE` puntato su una cartella temporanea, così cache e storico reali restano intatti.
  Riferisci i conteggi, la durata e i primi titoli. Poi lancia `analyze --watchlist` sul file
  prodotto e conferma che nessun titolo è bocciato su un criterio fondamentale o di
  trimestrale.
- [ ] **Passo 3:** riferisci all'utente cosa non è stato verificato. Il push lo decide lui.
