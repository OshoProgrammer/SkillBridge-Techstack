# SkillBridge Project Analysis

## Scope and preservation boundary

This analysis was completed before application-source changes. The repository is a single Vite/React/TypeScript application paired with an Express server. It has no committed database, tests, Docker files, CI configuration, or Python code.

### DO NOT MODIFY

The following legacy module is a hard compatibility boundary:

- OTP generation, hashing, expiry (10 minutes), verification, attempt limit (5), pending-registration storage, validation, and its API contracts in `server.ts`.
- Mailjet/Nodemailer SMTP integration in `server.ts`, including `createMailTransporter`, `resolveSmtpConfig`, `sendOtpEmail`, and `/api/auth/smtp-*` routes.
- OTP-related registration tables/storage semantics (currently the in-memory `pendingRegistrations` map; there are no database tables).
- OTP screens and user flow in `src/components/AuthLandingPage.tsx` and `src/components/AuthModal.tsx`.

The target Flask application must integrate around this module through a stable legacy OTP bridge; it must not reimplement it.

## Existing architecture and technology stack

| Area | Current implementation | Target implementation |
| --- | --- | --- |
| Frontend | React 19, TypeScript/TSX, Vite 6, Tailwind 4, Motion, Lucide | React in JavaScript/JSX, HTML/CSS (Tailwind may remain as CSS tooling) |
| Server | Node.js, Express 4 in one `server.ts` | Python, Flask REST API, structured blueprints/services/repositories |
| Authentication | scrypt password hashes plus opaque in-memory bearer sessions (8 hours) | JWT access tokens for Flask-owned APIs |
| OTP/email | Node crypto + Nodemailer SMTP, defaulting to Mailjet SMTP | Unchanged legacy Node module, isolated behind a bridge |
| Persistence | In-memory `DatabaseStore`, seed arrays, lost on restart | MySQL via SQLAlchemy and Alembic-compatible migrations |
| AI | `@google/genai` SDK; `gemini-3.7-flash` | Google Gen AI Python SDK; Gemini 2.5 model configured server-side |
| Serving | Express hosts Vite middleware/static SPA | Vite dev server plus Flask API; production reverse proxy/static host |

## Repository inventory

- `server.ts` (1,678 lines): all Express API routes, in-memory store, session auth, Mailjet-compatible SMTP/OTP, Gemini calls, Vite hosting.
- `src/types.ts`: TypeScript domain contracts for organization, personnel, courses, assessments, knowledge, AI drafts, and UI state.
- `src/data/seedData.ts` (2,089 lines): canonical demo seed state; this is the current schema/data source.
- `src/lib/scoring.ts`: deterministic competency scoring and learning-path business logic.
- `src/services/api.ts`: API client, bearer header injection, offline cache/queue, auth/OTP client calls.
- `src/context/AppContext.tsx`: application state, session presentation state, offline sync, local-only mentorship/external-course behavior.
- `src/App.tsx`: role/tab-based client-side view selection; no React Router.
- `src/components/`: auth, shell, navigation, modal, lock-screen, toast and walkthrough components.
- `src/components/views/`: 20 role-oriented views (dashboards, courses, assessments, knowledge, AI drafts, reports, people, credentials, alerts, settings).
- `vite.config.ts`, `tsconfig.json`, `package.json`, `bun.lock`, `package-lock.json`: frontend/build configuration.
- `.env.example`: Gemini and SMTP variables. `.env` is ignored. No production deployment files were found.

## Existing application flows

1. The provider initializes by fetching unauthenticated `GET /api/state`; it caches the full snapshot in `localStorage`.
2. Registered personnel log in with identifier/password; the server creates an opaque bearer session.
3. New personnel submit registration details; the legacy server sends a six-digit SMTP email OTP, verifies it, creates user/employee records, and returns a bearer session.
4. Six whitelisted demo personas can create a credential-free demo session.
5. Protected mutations update the in-memory state: role matrices, assessments, courses, knowledge resources, AI-draft pipeline, manager nudges, and offline sync.
6. AI can generate a structured knowledge draft or explain a learning path; deterministic fallback data is returned when Gemini is unavailable.
7. Client-side context manages tab routing, session UI, cache, an offline assessment queue, toasts, and several local-only UI mutations.

## API inventory

| Method and URL | Auth now | Purpose / key request body |
| --- | --- | --- |
| `GET /api/state` | No | Complete state snapshot (currently exposes `users` too) |
| `POST /api/reset-state` | Opaque bearer | Reset all seeded in-memory state |
| `POST /api/auth/login` | No | `identifier`, `password`, optional `role`; returns user, employee, session token |
| `POST /api/auth/demo-login` | No | Whitelisted `personaId`; returns demo session |
| `POST /api/auth/send-otp` | No | Registration details and password; dispatches legacy SMTP OTP |
| `POST /api/auth/verify-otp` | No | `email`, `otp`; creates user/employee and session |
| `GET /api/auth/smtp-status` | No | Legacy SMTP configuration status |
| `POST /api/auth/smtp-config` | No | Runtime SMTP configuration (legacy behavior) |
| `PUT /api/roles/:roleId/competencies` | Opaque bearer | Required competency matrix update |
| `POST /api/employees/:employeeId/assessments/submit` | Opaque bearer | Assessment answers, practical response, assessment type |
| `POST /api/employees/:employeeId/courses/:courseId/complete` | Opaque bearer | Course completion |
| `POST /api/knowledge/check-duplicate` | Opaque bearer | Title, competency, tags, department, description |
| `POST /api/knowledge/action` | Opaque bearer | Reuse, adapt, or create a knowledge resource |
| `POST /api/ai/extract-knowledge` | Opaque bearer | Raw document text and competency hint; structured AI draft |
| `POST /api/ai/drafts/pipeline-action` | Opaque bearer | Draft review/approval/publication action |
| `POST /api/manager/nudge` | Opaque bearer | Alert action/message |
| `POST /api/offline/sync` | Opaque bearer | Batch assessment submissions |
| `POST /api/ai/explain-path` | Opaque bearer | Role/competency/score explanation request |

Responses are JSON. Existing errors are mostly `{ success: false, error }` or `{ error }`; contract preservation requires retaining those shapes.

## Database inventory

There is no database driver, schema, migration, SQL query, index, or seed script. `DatabaseStore` copies in-memory seed arrays for: organization, departments, competencies, roles, employees, courses, assessments, knowledge resources, experts, badges, certificates, alerts, future skills, audit logs, users, scoring weights, and AI drafts. Password hashes, bearer sessions, and pending OTP registrations are separate in-memory maps.

The logical relationship graph is organization -> departments -> roles/employees/courses/resources; employees -> competency records/course completion/badges/certificates; courses -> assessments; AI drafts can publish courses, assessments and resources. These relationships must be represented in MySQL without deleting data. OTP state is excluded from schema conversion.

## Authentication and OTP flow

Passwords use Node `scryptSync` plus random salts. Login checks a password hash and returns a random opaque token stored in an in-memory session map. `requireAuthenticated` validates that token for all post-auth APIs. There is no logout endpoint; logout only clears the frontend token.

OTP registration creates and hashes a random six-digit code, emails it through Nodemailer/Mailjet SMTP, records it in `pendingRegistrations`, enforces the existing expiry/attempt controls, creates user/employee state after verification, and returns the opaque session token. SMTP configuration/status endpoints are used by the current auth UI. This flow must remain exactly untouched.

## AI flow

`getGeminiClient` reads `GEMINI_API_KEY` only on the server. `POST /api/ai/extract-knowledge` requests structured JSON and falls back to a deterministic draft. `POST /api/ai/explain-path` returns a short Gemini explanation or deterministic fallback. The current configured model is `gemini-3.7-flash`, which must change in the new Flask AI service to a configured Gemini 2.5 model. No AI credential reaches the browser.

## Frontend flow and state

The SPA uses `AppContext`; it has no URL router. `App.tsx` selects views from `currentTab` and `activeRole`. Forms live in components and call `src/services/api.ts`. The UI has Tailwind utility classes and the base stylesheet imports Tailwind. Local storage holds the offline snapshot, offline assessment queue, and sidebar preference. The auth landing/modal preserve a two-step OTP registration flow.

## Dependencies and configuration

Current runtime dependencies: `express`, `dotenv`, `nodemailer`, `@google/genai`, `react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `tailwindcss`, `motion`, and `lucide-react`. Development uses TypeScript, `tsx`, and esbuild. `.env.example` currently declares `GEMINI_API_KEY`, `APP_URL`, and SMTP variables. No JWT or MySQL dependency exists.

## Security concerns found before migration

- `/api/state` is unauthenticated and includes all users; it should not expose sensitive user/account records in the Flask API.
- `/api/auth/smtp-config` accepts runtime SMTP credentials unauthenticated. It is legacy and must not be altered under the OTP constraint; production must disable/exclude it at the network boundary and use environment configuration.
- Opaque sessions and all business state vanish on restart; no JWT, revocation, role enforcement, persistence, or CSRF strategy exists.
- Protected endpoints require authentication but generally do not enforce a role/ownership authorization policy.
- The full request body is accepted for many mutations; Flask migration needs validation and ORM parameterization.
- The existing Gemini model is not the target and its output parsing requires resilient validation.

## Migration classification

Files requiring migration or replacement: `server.ts` business/auth/API/AI portions (superseded by `backend/` except untouched OTP region), TypeScript frontend source files to `.jsx`/`.js`, TypeScript/Vite configuration, frontend API client, package scripts, and `.env.example`.

Files that can remain conceptually unchanged: seed values, deterministic scoring rules (port with parity tests), component markup/styles/behavior, Vite/Tailwind build approach, and dependency lockfiles until JavaScript conversion is complete.

Files/components that must remain untouched: OTP/EmailJet functions and routes in `server.ts`; `AuthLandingPage.tsx` and `AuthModal.tsx` OTP flows; legacy OTP-related maps and constants; Mailjet/Nodemailer behavior. They will be preserved as a legacy service, not ported.

## Migration risks

- The required Flask/JWT architecture conflicts with the immutable Node OTP service because OTP responses currently issue Node opaque sessions and mutate the same in-memory store.
- A process-local legacy OTP module cannot directly write Flask/MySQL data without an adapter; changing it would violate the preservation boundary.
- The full-state API and client-local mutations conceal server-side ownership/role gaps.
- No database schema exists, so initial MySQL schema is an inferred, documented representation of seed-data structures and must be validated against real production data before import.
- Converting all 10,000 lines of TSX mechanically to JS risks UI regression; component behavior and OTP screens need snapshot/manual verification.
