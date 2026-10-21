# Contributing

Thanks for helping. ilovestock is an educational tool, not financial advice: keep it that way in code, output and docs.

## Setup

Follow [Development](README.md#development) in the README: `pip install -e ".[dev]"`, then `npm install` in `web/` for the frontend.

## Before opening a pull request

```bash
ruff check .
ruff format --check .
pytest -m "not slow"
cd web && npm run lint && npm run build
```

CI runs the same checks on Python 3.11 and 3.13.

## Rules the code must keep

- **Indicator parameters are constants.** No options or config for SMA, Donchian, DMI/ADX periods.
- **Missing data is `N/D`, never `PASS`.**
- **Risk limits.** `risk_pct` above 2 is rejected; trade plans with reward:risk below 2 are discarded.
- **Default tests are offline.** They run on fixtures in `tests/fixtures/`. Anything that hits Yahoo or Finviz is marked `slow`.
- **Finviz is unofficial scraping.** Keep requests few and cached; don't add new live calls without a reason.
- **The web server listens on `127.0.0.1` only.** The PIN is a local lock, not authentication.

## Release

The web UI is built into `src/ilovestock/static/` and shipped as package data, so build the frontend before the Python package:

```bash
cd web && npm ci && npm run build && cd ..
python -m build
```

## License

By contributing you agree that your work is released under [GPL-3.0](LICENSE).
