# SkillBridge Migration Plan

## Compatibility decision

To satisfy both the Flask/JWT target and the explicit immutable OTP requirement, retain `server.ts` as an **unmodified legacy OTP/Mailjet service**. Flask owns all non-OTP REST APIs, MySQL persistence, JWT issuance/validation, authorization and Gemini 2.5. The browser continues to call the existing OTP endpoints unchanged through a reverse-proxy route to the legacy service. A narrow integration adapter exchanges a successful legacy OTP identity for a Flask JWT without copying or changing OTP logic. This is the minimum integration around, rather than a rewrite of, OTP.

## Phase 1 — Baseline and contracts

- Files affected: `PROJECT_ANALYSIS.md`, `MIGRATION_PLAN.md`.
- Files untouched: all application code, especially legacy OTP/email files and OTP UI.
- Work: record architecture, API/schema inventory, baseline lint/build, and contract fixtures.
- Tests: current lint/build baseline.
- Result: migration is traceable and compatibility decisions are explicit.

## Phase 2 — Flask foundation

- Files introduced: `backend/app/` with application factory, config, extensions, blueprints, services, repositories, schemas, utilities; `requirements.txt`; `wsgi.py`; Flask test configuration.
- Files untouched: `server.ts`, OTP UI components.
- Replace: Express business routes.
- Introduce: Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-JWT-Extended, Flask-CORS, Pydantic/Marshmallow-style validation.
- API: preserve non-OTP URL/method/body/response contracts where practical; document every unavoidable difference in `MIGRATION_REPORT.md`.
- Tests: app factory, health endpoint, error format, CORS.
- Risk: accidental coupling to Node’s in-memory store. Mitigation: all non-OTP state moves behind repositories.

## Phase 3 — MySQL schema and seed import

- Files introduced: SQLAlchemy models, Alembic migrations, idempotent seed importer, schema documentation.
- Files affected: Flask repositories/services only.
- Files untouched: legacy OTP pending-registration data and all OTP internals.
- Replace: `DatabaseStore` for non-OTP application state.
- Database changes: normalized tables for organizations, departments, competencies, roles, role requirements, employees, employee competency records/history, courses/modules, assessments/questions/sections, resources, experts, badges, certificates, alerts/history, future skills, audit logs, users, scoring weights, and AI drafts.
- Tests: migration up/down in a disposable database, seed idempotency, relationship/query tests.
- Risk: schema is inferred from demo seed data. Do not import/alter real data without backup and validated mapping.
- Result: data persists across restart and relationships are constrained/indexed.

## Phase 4 — Authentication and authorization

- Files introduced/affected: Flask auth service, JWT decorators, password service, role policy tests; frontend token handling only as necessary.
- Files untouched: OTP generation/verification/storage/expiry/API/frontend behavior and SMTP code.
- Replace: non-OTP opaque session checks with access JWTs; retain existing login request/response fields while returning JWTs from Flask.
- Integration: legacy OTP success is exchanged for a Flask JWT by an adapter; the OTP endpoint itself is not changed.
- Tests: valid/invalid credentials, JWT creation/validation/expiry/tampering, protected endpoint, role/ownership denial, OTP bridge mocked at its boundary.
- Risk: login and OTP identities must map to the same MySQL user without leaking credentials/tokens.

## Phase 5 — Business REST API parity

- Files affected: Flask route/controller/service/repository layers; frontend `api.js` only for base URL/token changes.
- Files untouched: all OTP endpoints and their frontend callers.
- Replace: Express implementations of state, scoring updates, assessments, courses, knowledge, AI draft pipeline, manager actions and offline sync.
- API changes: none intended for client-consumed non-OTP endpoints; authentication changes from opaque token to JWT. Any changed contract is recorded as OLD/NEW/REASON in the final report.
- Tests: endpoint contracts, validation, authorization and scoring parity against known fixtures.
- Result: frontend continues working with Flask endpoint parity.

## Phase 6 — Gemini 2.5 migration

- Files introduced: Flask AI service and mocked AI tests.
- Files untouched: unrelated UI and legacy OTP.
- Replace: Node `@google/genai` calls and `gemini-3.7-flash`.
- Introduce: Google Gen AI Python SDK, `GEMINI_MODEL` defaulted to a Gemini 2.5 model via environment.
- Tests: structured-output parsing, deterministic fallback, provider errors and no browser credential exposure.
- Risk: Gemini model availability/version changes. Mitigation: configuration plus mocks.

## Phase 7 — Frontend JavaScript conversion

- Files affected: `.tsx/.ts` React source becomes `.jsx/.js`; imports/config/package scripts updated; API client points to Flask while OTP URLs remain proxied unchanged.
- Files untouched: OTP screen markup, state transitions and request payloads. Conversion is syntax-only there.
- Replace: TypeScript-only syntax/tooling.
- Preserve: React UI, navigation, forms, styling, role views, offline cache/queue and all business behavior.
- Tests: frontend build, component smoke tests, manual OTP path regression.
- Risk: large mechanical conversion can alter JSX behavior. Mitigation: incremental conversion and build after batches.

## Phase 8 — Integration and operations

- Files introduced: reverse-proxy/development proxy config, Docker Compose optional local MySQL/Flask/legacy OTP topology, run documentation, `.env.example`.
- Files untouched: OTP/email source implementation.
- Dependencies: MySQL, Python virtual environment, Node only for legacy OTP and Vite/frontend build.
- Tests: browser-to-Flask API, legacy OTP proxy, JWT route, seeded MySQL, Gemini mocked integration.
- Result: one externally visible app while the immutable legacy OTP service is isolated.

## Phase 9 — Security and final verification

- Files affected: tests, security configuration, `MIGRATION_REPORT.md`.
- Review: secrets, CORS allow-list, JWT secret/TTL/algorithm, ORM parameterization, schema validation, XSS-safe rendering, log redaction, API authorization, and Gemini/database credential exposure.
- OTP rule: document legacy OTP risks separately; do not refactor it except a critical vulnerability explicitly authorized by the user.
- Required runs: backend tests, frontend tests/build, migration/seed tests, API/auth/JWT tests, mocked Gemini tests and OTP regression verification.

## Planned environment variables

`FLASK_ENV`, `FLASK_SECRET_KEY`, `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRES_MINUTES`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `DATABASE_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `CORS_ORIGINS`, `LEGACY_OTP_BASE_URL`, plus the existing untouched SMTP variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_SECURE`, `SMTP_FROM`).

## Expected end state

Flask/MySQL/JWT/Gemini 2.5 own the migrated application. React runs as JavaScript/JSX. The Node OTP/Mailjet implementation remains byte-for-byte intact and is accessed through a controlled compatibility boundary. The migration report will identify every created, modified and intentionally untouched file and every test result.
