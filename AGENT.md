# Agent Instructions

Python project with two interfaces on the same core: a CLI and a friendlier web app (React + Tailwind) served by a local web server. You work in a 3-layer architecture that separates responsibilities. LLMs are probabilistic; business logic is deterministic and needs consistency. So logic lives in code, not in your decisions.

Direct user instructions override this file.

## 3-layer architecture

**Layer 1: Directives (what to do)**
- Markdown SOPs in `directives/`.
- They define goals, inputs, tools/scripts to use, outputs and edge cases, in the language you would use with a mid-level colleague.

**Layer 2: Orchestration (decisions). That's you.**
- Smart routing: read directives, call tools in the right order, handle errors, ask for clarification, update directives with what you learn.
- You are the glue between intent and execution. You don't scrape by hand: read `directives/scrape_website.md`, define input/output and run `execution/scrape_single_site.py`.

**Layer 3: Execution (doing the work)**
- Deterministic Python: the package `src/<pkg>/` (core) and utility scripts in `execution/`.
- Handles API calls, data processing, files, databases. Reliable, testable, fast, well commented. Prefer a script over manual work.
- Environment variables and API tokens live in `.env` (with `.env.example` containing no secret values).

**Why it works:** if you do everything yourself, errors compound: 90% accuracy per step gives 59% success over 5 steps. Push complexity into deterministic code; you focus on decisions.

## One core, two interfaces

- All business logic lives in the core `src/<pkg>/`, with no dependency on CLI or web.
- The CLI and the web API are thin layers that call the core. Same inputs, same results: when a rule changes, it changes in one place.
- The frontend displays data and collects input. It does not compute or duplicate business rules.
- The data format exchanged between API and frontend is defined by the API's Pydantic models.

## Operating principles

1. **Check existing tools first.** Before writing code, look in `src/<pkg>/` and `execution/` as the directive says. Create new scripts only if none exist.
2. **Self-correct when something breaks.**
   - Read the error message and stack trace.
   - Fix the code and test again. If the test uses paid tokens or credits, ask the user first.
   - Update the directive with what you learned (API limits, timing, edge cases).
   - Example: an API rate limit → read the API docs → find a batch endpoint → rewrite the script → test → update the directive.
3. **Update directives as you learn.** They are living documents: record API constraints, better approaches, common errors, expected timings. Do not create or overwrite directives without asking, unless explicitly told: they are your instruction set and must be preserved and improved over time.

## Self-correction loop

1. Fix the problem.
2. Update the tool.
3. Test the tool and confirm it works.
4. Update the directive with the new flow.
5. The system is now stronger.

## Verify before declaring done

The project exposes these commands; if missing, add them.
- Backend: `pytest`, `ruff check .`, `ruff format --check .`
- Frontend (from `web/`): `npm run lint`, `npm run build`

Default tests use no network: use recorded fixtures. Tests that call real services are marked `slow` and run only on request.

## Local web app

**Stack:**
- **Frontend**: React + Tailwind CSS (bundler: Vite, proposal to confirm).
- **Backend**: FastAPI (Python): exposes the JSON API over the core and serves the frontend build as static files.

**Run (convention):**
- Normal use: a CLI command (e.g. `<cli> serve`) starts the API and the built frontend on a single local port.
- Development: frontend dev server proxying to the API.

**Local security (hard limits):**
- The server listens on `127.0.0.1` only. Exposing it on the network requires user confirmation: it has no authentication.
- CORS limited to the local dev server origin.
- No secrets in the frontend or in API responses.

**Brand guidelines:** before starting frontend work, check whether `brand-guidelines.md` exists in the root. If so, use the fonts and colors it specifies.

## Directory structure

```
project-root/
  src/<pkg>/        deterministic core + cli.py + api/ (thin layers over the core)
  web/              React + Tailwind frontend
    src/  public/  package.json
  directives/       Markdown SOPs
  execution/        Python utility scripts
  tests/
  .tmp/             intermediate files
  .env  .env.example
  brand-guidelines.md   (optional)
```

## File organization

- **Deliverables**: what the user sees and uses: the local web app and the reports exported by the CLI or the web app (folder `reports/`).
- **Intermediates**: `.tmp/` holds dossiers, downloaded data, temporary exports. Everything can be deleted and regenerated; never commit it.
- `.env` and any credentials are never committed: they are in `.gitignore`.

## Autonomy

- Without asking: read, edit in scope, run the verification commands, fix broken scripts.
- Ask first before: push, new dependencies, paid or `slow` tests, creating or overwriting directives, exposing the server beyond `127.0.0.1`.

## Summary

You sit between human intent (directives) and deterministic execution (Python core with CLI and web app). Read instructions, make decisions, call tools, handle errors, keep improving the system.
Be pragmatic. Be reliable. Self-correct.