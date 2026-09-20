# Coaching Platform Requirements

> This document describes the requirements **as implemented in the current codebase**
> (`generated/backend-app` Django + DRF API and `generated/frontend-app` React + Vite client).
> It is kept in sync with the code so re-running the developer agent should not contradict reality.

## Summary
- The platform supports three roles — administrator, coach, and coachee — secured with JWT authentication.
- Administrators onboard coaches and coachees; new accounts receive an emailed activation link and choose their own password before first sign-in.
- Coaches manage coachees, build coaching plans with sequenced kanban actions, hold discussions with @mentions, record insights, manage availability and sessions, and share resources/documents.

## User stories

### Authentication, roles, and onboarding
- As an administrator, I want to create and manage coach accounts, so that coaches can access the platform.
- As an administrator, I want to create and manage coachee accounts, so that coachees can be onboarded centrally.
- As a coach, I want to add my own coachees, so that I can manage the people I work with.
- As a new user, I want to receive an activation link by email when my account is created, so that I can verify my address and set my own password.
- As a new user, I want to be required to set a strong password on first sign-in, so that my account is secured before I use it.
- As a user, I want to change my password, so that I keep my account secure.

### Coaching plans and tasks
- As a coach, I want to manage a coaching plan with an overall goal, sequenced actions, a kanban-style board, and a target date, so that progress remains visible over time.
- As a coach, I want each plan action to have a title, description, kanban status, assignee, and sequence order, so that work is clear and ordered.
- As a coach or coachee, I want to add discussion to coaching tasks and plans and mention people with @mentions, so that everyone stays aligned on next steps.

### Coachees and insights
- As a coach, I want to search and filter coachee profiles with contact details and notes, so that coach workloads remain easy to manage.
- As a coach, I want to add insights to coachee profiles, so that progress can be reviewed over time.

### Sessions and availability
- As a coach, I want to manage weekly availability windows and unavailable periods, so that sessions are booked within approved time slots.
- As a coachee, I want to request and view coaching sessions (video, in-person, or phone) with my coaches, so that bookings stay organised.

### Resources and documents
- As a coach, I want to share coaching resources and one-to-one documents (optionally linked to a specific plan), so that shared materials remain easy to find.

## Functional requirements

### Authentication and authorisation
- The system shall authenticate users with JWT access/refresh tokens (`/api/auth/login`, `/api/auth/refresh`) and expose the current user via `/api/auth/me`.
- The system shall support user registration via `/api/auth/register`.
- The system shall distinguish administrator (staff), coach, and coachee roles and enforce role-based access on protected endpoints.

### Administration and onboarding
- The system shall allow administrators to create, list, update, and delete coach accounts (`/api/admin/coaches`).
- The system shall allow administrators to create, list, update, and delete coachee accounts (`/api/admin/coachees`) and browse a coach directory.
- The system shall email a single-use activation link when a coach or coachee account is provisioned; no password is ever transmitted.
- Accounts shall be created inactive with an unusable password until the activation link is redeemed, at which point the user sets their own password.
- The create-coachee response shall report whether the invitation email was sent (`invitation_sent`), and the UI shall warn the administrator when it was not; a mail failure shall not roll back account creation.
- The system shall allow users to change their password via `/api/auth/change-password`, clearing the forced-reset flag on success.

### Coaching plans and tasks
- The system shall allow coaches to create one or more coaching plans, each with a title, description, overall goal, status (to do / in progress / done), and target date, assigned to a coachee.
- The system shall return coaching plans ordered by target date.
- The system shall allow each plan to contain sequenced actions, each with a title, description, kanban status (backlog / in progress / done), assignee, order, and due date (`/api/plans/<id>/actions`).
- The system shall support discussion messages on plans and actions, including comma-separated @mentions.

### Coachees and insights
- The system shall allow coaches to manage coachees with name, email, and notes, optionally linked to a user account.
- The system shall allow coaches to add insights/journal notes to a coachee profile.

### Sessions and availability
- The system shall allow coaches to manage weekly availability windows and unavailable periods.
- The system shall allow sessions to be created and managed with a title, date, duration, mode (video / in-person / phone), and requester, optionally linked to a coaching plan.
- The system shall expose each coachee's coaches for calendar booking (`/api/calendar/my-coaches`).

### Resources and documents
- The system shall allow coaches to upload resource/document files with a title, description, category (guide / tool / template / article), and scope (shared / private), optionally linked to a coaching plan.
- The system shall scope resource access to the owner and serve uploaded media files in development.

## Non-functional requirements
- The API shall be secured with JWT authentication; protected endpoints require a valid bearer token.
- Passwords shall meet a complexity policy: minimum 12 characters with at least one uppercase letter, one lowercase letter, one digit, and one special character (enforced via `AUTH_PASSWORD_VALIDATORS` and a custom `PasswordComplexityValidator`).
- Activation tokens shall be generated with the `secrets` module, stored only as SHA-256 hashes, expire after `ACCOUNT_ACTIVATION_TOKEN_TTL_HOURS` (default 72), and be single-use; they shall never be returned in API responses.
- Email delivery shall be configurable via environment variables, with the backend selected in this order: an explicit `EMAIL_BACKEND`, then the Resend HTTP API when `RESEND_API_KEY` is set (the deployed default), then SMTP when `EMAIL_HOST` is set (`EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`/`EMAIL_USE_SSL`), and finally the console backend for local development.
- `DEFAULT_FROM_EMAIL` shall use a sender domain verified in Resend; the shared `onboarding@resend.dev` sandbox sender only delivers to the Resend account owner and is not usable for real coachees.
- Links in outbound email shall be absolute and derived from `FRONTEND_BASE_URL` (`FRONTEND_LOGIN_URL`, `ACCOUNT_ACTIVATION_URL`). Since the SPA has no client-side router and reads `?token=` from the root URL, `ACCOUNT_ACTIVATION_URL` shall point at the site root.
- Every deployed environment shall set `RESEND_API_KEY` and `DJANGO_SECRET_KEY`; falling back to the console email backend outside `DEBUG` shall emit a startup warning, since that backend reports sends as successful while delivering nothing.
- The frontend shall surface DRF field-level validation messages rather than a generic error.

## Constraints and assumptions
- Backend: Django + Django REST Framework with SQLite (development) and JWT via `rest_framework_simplejwt`.
- Frontend: React + Vite + TypeScript; the dev client must call the backend via `localhost` to satisfy CORS.
- Uploaded files are stored on the local filesystem (`MEDIA_ROOT`) and served only when `DEBUG` is enabled.

## Open questions / not yet implemented
- External calendar synchronisation with Microsoft Outlook and Google Calendar is specified but **not yet implemented**; the platform currently manages sessions and coach availability internally only.
- Real-time notifications for @mentions are not yet implemented; mentions are stored and displayed but not pushed.
- Coachee profile photos referenced in earlier drafts are not part of the current data model.

## Sources
- Codebase: `generated/backend-app` (Django/DRF API) and `generated/frontend-app` (React/Vite client)
- Original intake: text-1
