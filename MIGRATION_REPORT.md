# Migration Report (incremental migration checkpoint)

## Original and target stack

The original application used React 19 + TypeScript/Vite/Tailwind and a monolithic Express/Node server with in-memory state, opaque bearer sessions, Nodemailer/Mailjet-compatible SMTP OTP, and `@google/genai`. This checkpoint introduces the Flask/Python REST foundation, JWT, MySQL SQLAlchemy configuration, and Google Gen AI Python SDK configuration for Gemini 2.5.

## Created

- `PROJECT_ANALYSIS.md` — complete pre-change repository analysis.
- `MIGRATION_PLAN.md` — incremental conversion plan and explicit OTP boundary.
- `requirements.txt` — Flask, JWT, SQLAlchemy/MySQL, Alembic and Google Gen AI dependencies.
- `backend/app/` — Flask factory, configuration, extensions, persistence models, state/auth/AI services, and REST blueprints.
- `backend/seed.py` — safe, explicit state-import command; it does not touch OTP pending registrations.
- `backend/tests/test_api.py` — JWT login/protected-route and invalid-credential tests.
- `wsgi.py` — WSGI entry point.

## Modified

- `.env.example` now documents Flask/JWT/MySQL/Gemini 2.5/CORS/legacy-OTP variables without real credentials.
- `.gitignore` excludes the local Python environment and Python caches.

## Intentionally untouched components

- `server.ts`, including the complete OTP generation, hashing, verification, expiry, attempts, pending-registration storage, and Mailjet/Nodemailer SMTP implementation.
- All OTP endpoints’ legacy implementation and behavior: `/api/auth/send-otp`, `/api/auth/verify-otp`, `/api/auth/smtp-status`, `/api/auth/smtp-config`.
- `src/components/AuthLandingPage.tsx` OTP flow.
- `src/components/AuthModal.tsx` OTP flow.
- OTP-related database/storage semantics (currently legacy in-memory maps).

Flask exposes transparent transport routes for these endpoints. Those routes do not inspect or implement OTP logic; their purpose is only to keep the legacy service isolated.

## API/JWT/Gemini changes

- Flask provides `GET /health`, `POST /api/auth/login`, `GET /api/state`, `POST /api/ai/explain-path`, `POST /api/ai/extract-knowledge`, and `POST /api/offline/sync`.
- Flask login returns a JWT generated server-side. Protected Flask routes require it.
- Gemini calls use the Google Gen AI Python SDK and `GEMINI_MODEL` default `gemini-2.5-flash`; deterministic fallback output remains available when credentials/provider are unavailable.
- A MySQL-configured JSON aggregate store persists the legacy state shape as an interim compatibility layer. Normalized MySQL tables and all endpoint parity remain pending.
- Vite development traffic for `/api` now targets Flask. Flask uses a narrow legacy adapter only for OTP/SMTP endpoints. Successful legacy OTP and demo authentication responses are exchanged for a Flask JWT while retaining the existing response fields required by the protected auth UI.

## Database changes

Introduced SQLAlchemy models `application_state` and `user_credentials`. The first preserves existing seed/API shapes in a MySQL JSON column; the second stores Flask-side password hashes. No existing database or OTP data was changed, deleted, or migrated because none exists in the repository.

## Dependencies

Added Python dependencies listed in `requirements.txt`. The frontend remains TypeScript at this checkpoint; converting every TS/TSX file to JavaScript/JSX was not performed because that would require a separately verified, large mechanical migration.

## Tests and verification

- Existing frontend static type check: passed before changes (`npm run lint`).
- New backend tests: passed (`3` assertions across JWT login/protected-route, invalid credentials, missing token, and invalid JWT rejection). Run with `.venv/bin/pytest -q`.
- Python syntax validation: passed (`.venv/bin/python -m compileall -q backend wsgi.py`).
- Frontend static type check: passed (`npm run lint`).
- Frontend/legacy build artifacts: produced successfully (`dist/index.html` and `dist/server.cjs`). The existing frontend source was intentionally not mechanically converted in this checkpoint.
- OTP regression: not run. The legacy server could not start in the sandbox because `tsx` failed creating its IPC socket (`EPERM`). No OTP source was changed.

## Security findings

- Flask configuration takes JWT/MySQL/Gemini secrets from environment only.
- Flask’s state response suppresses the user list to avoid the original unauthenticated account-data exposure.
- The unauthenticated legacy SMTP configuration endpoint remains a documented legacy risk. It was not changed per the OTP/EmailJet preservation requirement; limit it at the reverse-proxy/network boundary in production.
- The legacy OTP response currently returns an opaque legacy session token, so the complete token-exchange bridge and frontend migration must be completed before Flask-protected routes can follow a new OTP registration.

## Known issues / remaining migration work

1. Complete normalized MySQL schema/migrations and seed export/import.
2. Port the remaining business endpoints with contract-parity tests.
3. Implement the OTP-success-to-Flask-JWT identity exchange without modifying the OTP implementation.
4. Convert React TypeScript source to JavaScript/JSX incrementally and verify every screen, preserving OTP markup/flow.
5. Add Docker/reverse proxy topology, CORS allow-list deployment values, and full integration tests.
6. Install dependencies in a functioning Python environment and run all tests.

## Run instructions

1. Create environment: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
2. Configure `.env` from `.env.example` with real deployment secrets.
3. Create MySQL database/user, then seed a sanitized legacy state export: `DATABASE_URL=... .venv/bin/python -m backend.seed state.json`.
4. Run Flask: `FLASK_APP=wsgi.py .venv/bin/flask run --port 5000` (or `npm run backend`).
5. Run the untouched legacy OTP service separately: `npm install && npm run legacy:otp` (port 3000 by its existing implementation).
6. Run the React development server: `npm run dev` (port 5173; it proxies `/api` to Flask).
6. Configure Vite/reverse proxy so Flask receives `/api` and proxies only `/api/auth/{send-otp,verify-otp,smtp-status,smtp-config}` to the legacy service.
7. Run backend tests: `.venv/bin/pytest backend/tests -q`; run current frontend checks: `npm run lint && npm run build`.
