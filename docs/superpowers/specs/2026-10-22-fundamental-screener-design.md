---
type: design
date: 2026-10-22
status: approvato
tags: [ilovestock, screener, fondamentali, qualità]
---

# Screener dei fondamentali con punteggio di qualità

## Perché

Oggi l'utente cerca titoli nuovi con uno screener esterno e passa la lista a `ilovestock analyze`.
Lo screener esterno non ha gli stessi criteri del metodo, quindi la lista arriva piena di titoli
che `analyze` poi boccia. Serve uno screener interno che applichi **esattamente** i criteri
fondamentali del metodo a tutto il mercato USA e restituisca una lista breve e ordinata per
qualità, pronta da passare ad `analyze` per la parte tecnica.

Le vendite in crescita da sole non bastano: un'azienda può vendere di più con margini più bassi.
Per questo i titoli si ordinano con un punteggio di qualità, non per crescita delle vendite.

## Obiettivi

1. **Comando `ilovestock screen`** e **pagina Screener nella web app**, sullo stesso core.
2. **Universo:** tutte le azioni quotate su NASDAQ, NYSE e AMEX, come `analyze`, comprese le
   aziende estere quotate negli USA (ADR, per esempio NIO). Finviz copre solo queste borse, quindi
   nell'URL non va il filtro di paese `geo_usa`, che terrebbe solo le aziende con sede negli USA
   (decisione dell'utente).
3. **Filtro:** tengono solo i titoli che passano **tutti** i criteri fondamentali e di
   trimestrale che usa `analyze`, con le soglie del file di config. N/D non passa mai.
4. **Limite:** prima di lanciare la ricerca l'utente sceglie il numero massimo di titoli
   (default 20, massimo 50). Se ne passano di più, si tengono i primi N per punteggio di qualità.
5. **Punteggio di qualità** (sotto) visibile nei risultati dello screener, con una nota per titolo
   che spiega da dove viene.
6. **Riga "Quality" informativa** nel dettaglio di `analyze` (web e `--detail`) con ROIC e
   variazione del margine operativo, senza punteggio.
7. **Uscita:** lista di ticker da passare ad `analyze` (watchlist su file nel terminale, pulsanti
   nella web app).

## Non obiettivi

- Screener al contrario (prima i criteri tecnici, poi i fondamentali). Sarà un progetto a parte.
- Analisi tecnica dentro lo screener: la fa `analyze` dopo.
- Salvare le ricerche dello screener nello storico. Lo storico resta solo per le analisi.
- Ricerche programmate, notifiche, mercati non USA.
- Nuove fonti dati o nuove dipendenze: si usano Finviz e yfinance già presenti.

## Anti-obiettivi (sarebbe un fallimento anche se funziona)

- Un titolo che lo screener dà come "tutti pass" e che `analyze`, lo stesso giorno con la stessa
  config, boccia su un criterio fondamentale o di trimestrale. Il giudizio deve essere identico.
- Il punteggio di qualità che cambia il verdetto BUY / NO-BUY, la matrice delle regole o i motivi
  di NO-BUY di `analyze`.
- Richieste a Finviz o Yahoo senza un tetto. Ogni ricerca ha un numero massimo di candidati.
- Test o server di prova che scrivono nello storico o nella config reali.

## Come funziona la ricerca

1. **Pre-filtro su Finviz.** Dalla config si costruisce un URL dello screener Finviz. I filtri
   sono: nessun filtro di paese; crescita vendite ed EPS (`Sales Q/Q`, `EPS Q/Q`, che su Finviz sono anno su anno);
   ROE; proprietà istituzionale; transazioni istituzionali positive. Finviz ha soglie a
   scaglioni: per ogni soglia si prende lo scaglione **più largo** che non scarta titoli validi.
   - *Corretto dopo la review Codex del 2026-10-23:* dividendo e capitalizzazione non sono più
     filtri Finviz. Il filtro dividendi di Finviz usa la stima futura, mentre la regola usa gli
     ultimi 12 mesi, quindi poteva scartare titoli validi. Il filtro di capitalizzazione accetta
     una sola fascia (l'intervallo libero è solo Elite), quindi non poteva escludere large e
     giant. Ora l'URL ordina per capitalizzazione decrescente (`o=-marketcap`) e
     `screener.candidates` legge le righe con `providers/finviz.py::screener_rows`. Salta large
     e giant, si ferma alla prima nano e usa le fasce di `market_cap_band`, le stesse della
     regola. Se le righe non sono in ordine la ricerca si ferma con un errore, perché fermarsi
     alla prima nano sarebbe sbagliato.
   - *Scelta di Claude, perdita accettata:* lo screener Finviz scarta i titoli che non hanno il
     dato filtrato. `analyze` invece, per crescita, ROE, proprietà istituzionale e market cap,
     ripiega su Yahoo. Un titolo con `-` su Finviz in uno di quei campi può quindi passare
     `analyze` ma non entrare mai fra i candidati. Sono casi rari, di solito titoli con pochi
     dati. Va scritto nell'help del comando e nella pagina: "solo titoli con dati Finviz
     completi".
   - Se `growth_basis = "qoq"`, i filtri di crescita non vanno nell'URL, perché Finviz ha solo il
     confronto anno su anno. Li applica la verifica esatta. *Scelta di Claude:* se così i
     candidati superano il tetto, il messaggio di rifiuto suggerisce anche `growth_basis = "yoy"`.
   - I codici dei filtri vanno presi da una risposta reale di Finviz, non indovinati (regola di
     `PROJECT.md`). Serve una richiesta dal vivo, da chiedere prima all'utente, e la pagina va
     salvata come fixture.
2. **Tetto sui candidati.** Se il pre-filtro restituisce più di `MAX_CANDIDATES` titoli micro,
   small o mid (valore 100), la ricerca si ferma e chiede soglie più strette. 100 tiene una ricerca sotto i 5 minuti circa, quindi `/api/screen` può restare
   una richiesta sincrona come `/api/analyze`, senza job in background. L'utente ha deciso di
   tenere 100 senza misurare prima il numero reale di candidati: se le sue soglie ne danno di
   più, le stringe lui.
3. **Verifica esatta.** Per ogni candidato si usano gli stessi passi di `analysis.analyze`:
   `provider.history`, `provider.fundamentals`, `rules.fundamental.fundamental` e
   `rules.earnings.earnings`. Passa solo chi ha tutti i risultati PASS. Sono i criteri della
   tabella Fundamental di `analyze`. *Scelta di Claude:* `post_earnings` ("After last earnings")
   resta fuori. In `analyze` sta fra i criteri tecnici, ed è un'attesa di pochi giorni, non un
   giudizio sull'azienda. Se entrasse nel filtro, nasconderebbe un buon titolo proprio nei giorni
   dopo la trimestrale. Un errore di dati su un
   titolo lo esclude e viene contato, senza fermare la ricerca. Le cache del giorno (prezzi e
   fondamentali) si riempiono, quindi l'`analyze` successivo sugli stessi titoli parte dalla cache.
4. **Qualità e classifica** sui titoli che passano (sotto). Si tengono i primi N.

Ricerca lenta: qualche secondo per candidato. Nel web, come per `analyze`, si mostra un messaggio
di attesa.

## Punteggio di qualità

Misura se la crescita crea valore, non solo fatturato.

- **ROIC** (rendimento del capitale investito): campo Finviz `"ROIC"` dello snapshot che
  `FinvizProvider.fundamentals` già scarica (chiave verificata in
  `tests/fixtures/*_finviz.json`, formato `"72.08%"`). Nuovo campo `roic_pct` su `Fundamentals`.
- **Variazione del margine operativo in un anno**, in punti percentuali: margine operativo
  dell'ultimo trimestre meno quello dello stesso trimestre dell'anno prima. Il margine è
  `Operating Income / Total Revenue` dal `quarterly_income_stmt` di Yahoo, che il provider già
  legge. La fixture `HZO_income.csv` ha 5 trimestri, quindi si confronta il trimestre 0 con il 4.
  N/D se mancano i dati o se il fatturato è <= 0.
- **Punteggio** (0-100, calcolato solo nello screener): fra i titoli che passano tutti i filtri,
  ognuno ha una posizione per ROIC e una per variazione del margine (più alto = meglio). Ogni
  posizione diventa un percentile da 0 a 100, dove 100 è il migliore del gruppo. Il punteggio è
  la media dei due percentili. Si usano le posizioni e non i valori grezzi, così un valore
  estremo non schiaccia gli altri.
  - *Scelta di Claude:* un valore N/D prende la posizione peggiore per quella misura. Il titolo
    resta in lista, perché la qualità non è un criterio del metodo.
  - *Scelta di Claude:* a parità di punteggio vince il ROIC più alto.
  - Gruppo di un solo titolo: ogni misura disponibile vale 100, una misura N/D vale comunque 0
    (la regola "N/D = posizione peggiore" prevale). Con entrambe N/D il punteggio è 0.
- **Nota per titolo** (dettaglio nello screener), per esempio: `ROIC 31.2% → #2 di 47 · margine
  operativo 14.0% → 18.1% (+4.1 pt) → #3 di 47 · punteggio = media delle due posizioni, 0-100`.

## Interfacce

### Terminale

`ilovestock screen [--max N] [--out FILE] [--config FILE]`

- `--max` va da 1 a 50 (il limite di `analyze`), con default 20.
- Stampa la tabella: posizione, ticker, market cap con fascia, ROIC, variazione del margine,
  punteggio. Prima della tabella dice quanti candidati ha trovato il pre-filtro, quanti passano
  tutti i criteri e quanti ne mostra. Il disclaimer e l'avviso su Finviz sono gli stessi di
  `analyze`.
- Salva la lista come watchlist, un ticker per riga, leggibile da `inputs.read_watchlist`.
  *Scelta di Claude:* il default è `reports/screen-AAAA-MM-GG.txt`, la stessa cartella dei
  report di `analyze`.
- Alla fine stampa il comando da lanciare: `ilovestock analyze --watchlist <file>`.
- Se nessun titolo passa, lo dice, non salva il file ed esce con codice 0.

### Web app

- Nuova voce **Screener** nella sidebar, con la route `#screener`.
- La pagina ha un campo "Max results" (default 20, da 1 a 50) e il pulsante **Search**.
- Sopra la tabella c'è una riga di conteggio, per esempio "47 stocks pass every fundamental
  rule · showing the top 20 by quality score".
- La tabella ha le colonne #, Ticker, Market cap (con fascia), ROIC, Op. margin Δ (1y) e Quality
  score. Ogni riga si apre e mostra la nota. I pulsanti stanno sotto la tabella. La bozza
  approvata è in `.superpowers/brainstorm/1852-1792680538/content/quality-placement.html`, che
  non è nel repo.
- **Analyze these N** apre la pagina Analysis con il campo Tickers già compilato. *Scelta di
  Claude:* l'analisi non parte da sola, la lancia l'utente.
- **Save as watchlist** scarica un `.txt` con un ticker per riga.
- Nuovo endpoint `POST /api/screen` (`{max: int}`), protetto dal PIN come `/api/analyze`, con le
  stesse regole di errore. Il risultato vive solo nella sessione del browser, come l'ultima
  analisi.
- Le etichette della UI restano in inglese, come nel resto dell'app.

### Dettaglio di `analyze`

- Ultima riga della tabella Fundamental, con nome **Quality**, valore `ROIC x%, op. margin ±y pt`
  e stato **INFO**.
- È solo una riga mostrata: il dato sta fuori dalla lista dei criteri, quindi verdetto,
  matrice delle regole (8 fondamentali + 4 tecnici), motivi di NO-BUY, colonne "FAIL / N/D" e
  criteri salvati nello storico restano identici.
- Compare sul web e in `analyze --detail`. Nella tabella riassuntiva del terminale no.

## Vincoli

- Il core resta unico per CLI e web. La CLI è solo uno strato sottile, senza regole (`cli.py`).
- Niente rete nei test di default né in CI. Pre-filtro, verifica e qualità si provano su fixture
  registrate. Ci vuole almeno una pagina reale dello screener con l'URL generato.
- Le chiavi dei campi Finviz e i codici dei filtri si prendono da risposte reali (`PROJECT.md`).
- Ogni richiesta dal vivo a Finviz (nuove fixture, prove reali) va chiesta prima all'utente.
- Per le prove si usano solo PIN, config e storico in una cartella temporanea.
- `ruff check .`, `ruff format --check .`, `pytest -m "not slow"`; in `web/` `npm run lint` e
  `npm run build`.

## Lasciato al builder

- Come comporre l'URL (parametri, ordine, gestione delle fasce di capitalizzazione) entro i
  vincoli sopra.
- Dove mettere il codice: un modulo nuovo (per esempio `screener.py`) o funzioni in quelli che
  ci sono già.
- Il formato esatto della nota e le larghezze delle colonne.
- Come mostrare l'avanzamento nel terminale. Il web mostra il messaggio di attesa.
- Se la riga Quality debba comparire anche negli export MD/CSV/JSON di `analyze`.
