# iLoveStock landing page

Public presentation site for iLoveStock. React 19 + Vite + Tailwind 4, animated with [Motion](https://motion.dev).
Brand: `../brand-guidelines.md`. It is a static site: it does not call the Python core or the API.

```bash
cd landing
npm ci
npm run dev      # http://localhost:5173
npm run lint && npm run build   # tsc + vite build into dist/
```

## Deploy on Vercel

Import the repository, set **Root Directory** to `landing`. Vercel detects Vite: build command
`npm run build`, output directory `dist`. No environment variables.

All figures on the page are illustrative and labelled as such; the rule names and thresholds are the
defaults of `src/ilovestock/config.py`. Update them if those defaults change.
