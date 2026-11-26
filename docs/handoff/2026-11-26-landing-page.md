---
type: handoff
date: 2026-11-26
status: pronto-per-review
seq: 1
prev: nessuno
tags: [landing, vercel, react, motion, brand]
---

# Handoff: landing page pubblica

## Obiettivo

Sito pubblico di presentazione del prodotto, da pubblicare su Vercel, quindi stack React. Deve seguire grafica e colori di `brand-guidelines.md` e usare Motion per transizioni ed effetti. Vive in una cartella propria (`landing/`) sul branch `feat/landing-page`, separata da `web/` (l'app locale) e dal core Python.

## A che punto siamo

- Funziona: `landing/` completa (hero con pannello verdetto animato, metodo, trade plan con grafico che si disegna, screener, modi d'uso con blocco di installazione, fascia "What it does not do", footer). `npm run lint` e `npm run build` passano.
- Verificato con screenshot reali (desktop 1360 px, mobile 390 px) tramite Chrome DevTools Protocol: sequenza del pannello, toggle tra i due campioni, grafico, layout mobile.
- **Push annullato (2026-11-26)**: il commit iniziale era stato pushato, poi il branch remoto è stato cancellato e il commit annullato in locale, perché la prima versione pubblicava soglie e parametri della strategia. Il copy è stato poi generalizzato (solo aree analizzate).
- **Al momento nulla è committato né pushato.** Il branch `feat/landing-page` esiste, i file sono untracked (`landing/`) più la modifica a `.gitignore`.
- Non fatto: deploy reale su Vercel, test di `prefers-reduced-motion`, job CI per `landing/`, test Lighthouse/accessibilità automatici.

## Cosa abbiamo provato che NON ha funzionato

- **Screenshot con `chrome --headless --screenshot --virtual-time-budget`**: il tempo virtuale congela `requestAnimationFrame`, quindi le animazioni di Motion restano ai primi frame (pannello quasi vuoto, grafico non disegnato). Soluzione: script CDP in tempo reale (`shot.mjs` nello scratchpad della sessione, non nel repo) che lancia Chrome con `--remote-debugging-port`, attende alcuni secondi veri e fa `Page.captureScreenshot`.
- **Heredoc bash molto lungo per scrivere `App.tsx`**: la shell ha dato "unexpected EOF". Soluzione: usare lo strumento Write per i file grandi.
- **Primo layout del pannello hero** (nome criterio e soglia su due righe): il pannello superava la viewport e il verdetto finiva sotto la piega. Ora soglia inline su `sm+`.

## Problemi incontrati e come li abbiamo risolti

- Badge PASS/FAIL su riga propria in mobile: sintomo = badge a capo sotto il valore; causa = `col-span-2` sul contenitore del badge; correzione = griglia `[1fr_auto_3.5rem]` anche su mobile.
- Etichette del grafico troppo piccole su telefono (SVG scalato a ~0.6): font a 18/17 e `X1 = 456`.
- `vite preview` lascia un lock: un secondo avvio fallisce con "Found another Vite preview process". Chiudere il primo (o `--bypass-lock`) prima di rilanciare.

## Decisioni prese

- **Cartella `landing/` con package.json proprio** (non dentro `web/`): scartato riusare `web/` perché quello builda dentro il pacchetto Python (`src/ilovestock/static/`) ed è dietro PIN; Vercel vuole una Root Directory autonoma.
- **Stack identico a `web/`** (Vite, React 19, Tailwind 4, fontsource) più `motion`: scartato Next.js perché è un sito statico di una pagina, serve solo `dist/`.
- **Copy in inglese**, come README e app: scartato l'italiano perché il prodotto e il pubblico US-stocks sono in inglese (da confermare con l'utente).
- **Tema chiaro (#EEF3F6) con pannello verdetto scuro e fascia Limits scura**: scartata una pagina tutta scura/crema+terracotta (default "da AI"); il brand chiede "trustworthy".
- **Limiti con lo stesso peso dei benefici** (fascia a tutta larghezza, non fine print): imposto dal brand ("Show fees, risks, and terms with the same visual weight as benefits").
- **Valori illustrativi dichiarati come tali (ticker fittizi, nessuna soglia)** (ticker `SMPL`/`DEMO`, "Company A–E"): scartati ticker reali per non far sembrare una raccomandazione; nessuna soglia reale è riportata.
- **Motion solo dove risponde a un'azione o racconta qualcosa**: sequenza hero, toggle con `layoutId`, grafico al primo ingresso in viewport, barre del ranking, feedback "Copied". Scartati fade-in per ogni sezione. `MotionConfig reducedMotion="user"` più `useReducedMotion` per `pathLength`/delay.
- **Niente commit e niente modifica a `ci.yml`**: non richiesti; CLAUDE.md dice di chiedere per cose fuori scopo.

## File toccati

- `.gitignore`: aggiunto `landing/node_modules/`.
- `landing/package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`, `eslint.config.js`, `index.html`: scaffolding (config copiata da `web/`, `index.html` con meta description/og).
- `landing/public/logo.png`: copia di `web/public/logo.png`.
- `landing/src/index.css`: token brand in `@theme` (con tinte derivate per contrasto), font, focus.
- `landing/src/data.ts`: campioni, serie del grafico, `PLAN`, `RANKING`, `REPO`.
- `landing/src/Verdict.tsx`: pannello hero animato.
- `landing/src/TradePlan.tsx`: grafico SVG animato.
- `landing/src/App.tsx`: header, hero, sezioni, footer.
- `landing/README.md`: comandi e istruzioni Vercel (Root Directory = `landing`).

## Dove vogliamo andare

1. Chiedere all'utente di confermare la lingua (inglese vs italiano/bilingue) e rivedere il copy.
2. Fare il commit sul branch `feat/landing-page` (se l'utente conferma) e aprire la PR; per il commit, messaggio terminato dalla riga Co-Authored-By indicata nel system reminder.
3. Importare il repo su Vercel con Root Directory `landing`, verificare il deploy di anteprima.
4. Valutare un job `landing` in `.github/workflows/ci.yml` (lint + build, `working-directory: landing`, cache su `landing/package-lock.json`).
5. Opzionale: og:image, `prefers-reduced-motion` provato a mano, Lighthouse.

## Da sapere prima di toccare qualcosa

- Non servono richieste live a Finviz/Yahoo per questo lavoro; la landing è statica e non chiama il core né l'API.
- **Regola di pubblicazione**: la pagina nomina solo le aree analizzate e non pubblica soglie né parametri degli indicatori (né il metodo del punteggio di qualità, né i limiti di rischio esatti). Valori e numeri sono illustrativi; non reintrodurre dettagli della strategia nel copy.
- Su Windows lo screenshot con Chrome richiede il path `C:/Program Files/Google/Chrome/Application/chrome.exe`; usare il server su `http://localhost:4173` (non `127.0.0.1`: ascolta solo su localhost).
- Il pannello hero usa `key` per rimontare la lista e rifare la sequenza al cambio campione: non rimuoverlo.
