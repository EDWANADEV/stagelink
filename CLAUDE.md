# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

StageLink is a platform that connects companies and students around internships (stages). It is a Django 6 / Python 3.14 project generated from Cookiecutter Django and managed with `uv`.

## Team rules (mandatory for every file created or modified)

1. **Identifiers in English**: variables, functions, classes, models, DB fields, view files (e.g. `VerificationCode`, `is_profile_completed`).
2. **Comments, docstrings and explanatory messages in French only.** User-facing strings are French too (`LANGUAGE_CODE = "fr"`), wrapped in `gettext_lazy` / `{% translate %}`.
3. **PEP 8**: 4-space indentation, short single-responsibility functions, imports grouped stdlib → Django/third-party → local apps.
4. **Local development uses `uv`, not Docker**: run everything with `uv run python manage.py …`.
5. **No DRF for new features**: use classic Django views. `JsonResponse` is allowed only when client-side JavaScript requires it. Prevent N+1 queries with `select_related()` / `prefetch_related()`.
6. **Workflow**: the current focus is finishing authentication and profiles. Run the tests locally, then prepare a pull request before moving on.

## Commands

Local (host) workflow with `uv`:

```bash
uv run python manage.py runserver
uv run python manage.py makemigrations && uv run python manage.py migrate
uv run pytest                                   # all tests (uses config.settings.test, --reuse-db)
uv run pytest stagelink/offers/tests.py         # one file
uv run pytest stagelink/users/tests/test_views.py::TestClass::test_name   # one test
uv run pytest --create-db                       # after migration changes, since --reuse-db is the default
uv run coverage run -m pytest && uv run coverage html
uv run mypy stagelink
uv run ruff check --fix . && uv run ruff format .
uv run djlint --reformat stagelink/templates    # template formatting (djLint, Django profile, 2-space indent)
uv run celery -A config.celery_app worker -l info   # run from the repo root (next to manage.py)
uv run celery -A config.celery_app beat
```

Tailwind CSS v4 (CLI, no PostCSS/webpack). `stagelink/static/css/output.css` is generated from `input.css` and committed:

```bash
npm run dev     # watch
npm run build   # minified
```

Tests need a Postgres user with the `CREATEDB` privilege (pytest-django creates `test_<db>`).

Docker workflow via `just` (exists but is **not used for development**; uses `docker-compose.local.yml`: django, postgres, redis, mailpit on :8025, celeryworker, celerybeat, flower on :5555):

```bash
just up | down | logs | build
just manage <cmd>       # e.g. just manage migrate
just pytest <args>
```

Pre-commit runs ruff (lint and format), django-upgrade (`--target-version 6.0`), pyproject-fmt, and djLint. Ruff enables a very broad rule set with isort `force-single-line = true`, which means one import per line. Migrations are excluded from linting.

## Configuration

- Settings split: `config/settings/{base,local,test,production}.py`. `base.py` reads the root `.env` (unless `DJANGO_READ_DOT_ENV_FILE=False`). The Docker setup reads `.envs/.local/.django` and `.envs/.local/.postgres` instead.
- DB: PostgreSQL via `DATABASE_URL` or the `POSTGRES_*` vars. `ATOMIC_REQUESTS = True`.
- Project-specific env settings: OTP (`OTP_EXPIRATION_MINUTES`, max attempts, length, cooldown), upload limits (CV, company logo), Stripe and Flutterwave keys and webhook secrets, review rating bounds, and separate Redis URLs (`REDIS_URL`, `REDIS_OTP_URL`, `REDIS_SECURITY_URL`).

## Architecture

Local apps live under `stagelink/` and are registered in `LOCAL_APPS`: `users`, `core`, `profiles`, `offers`, `application`, `notifications`, `donation`, `payments`, `reviews`.

### Domain layering (follow this pattern in every app)

- **`core.models.BaseModel`**: an abstract base for all domain models. It provides a UUID PK, `created_at`/`updated_at`, `created_by`/`updated_by` audit FKs, and **soft delete** (`is_deleted`, `soft_delete()`, `restore()`). `objects` hides soft-deleted rows. Use `all_objects` when deleted rows must be included (for example, payments do this when locking rows). Ownership checks use `created_by`.
- **`services.py`**: holds all business logic as plain functions or `*Service` classes with static methods, often `@transaction.atomic`. Services whitelist input fields (see `OFFER_INPUT_FIELDS` / `_clean_offer_data` in `offers/services.py`) so callers can't set `company`, `status`, `created_by`, and similar fields. Services raise Django `ValidationError` / `PermissionDenied`.
- **`permissions.py`**: contains `require_*` guard functions (`require_company`, `require_admin`, `require_offer_owner`, …). Each one raises `PermissionDenied` and is called at the top of service functions. These are not DRF permission classes.
- **`views.py`**: mostly still stubs in the domain apps. Only `users` and `profiles` have real views and URLs so far, so new UI work wires views to the existing services.
- Shared choices all live in `stagelink/utils/enums.py` (`Role`, `OfferStatus`, `ApplicationStatus`, `PaymentStatus`, …). Add new `TextChoices` there instead of defining them per app.

### Users and auth

- The custom `users.User` has no username. It uses email login with a `role` (`STUDENT` / `COMPANY`) and an `email_verified` flag. Company and student data live in `profiles.CompanyProfile` / `StudentProfile` (accessed as `user.company_profile`).
- allauth is installed, but signup, signin, and password reset are **custom views** in `users/views/` that use an **OTP flow**. `users/services/otp_service.py` handles creation and verification with hashed codes, attempt limits, and Redis-backed cooldowns. `otp_email_service.py` sends the emails, and `password_reset_token_service.py` handles reset tokens. URLs follow the pattern `users/verify-otp/<purpose>/<token>/`.
- `users.middleware.ProfileCompletionMiddleware` (last in `MIDDLEWARE`) forces logged-in, non-staff users through OTP email verification (reusing the session's `pending_signup_token` or sending a new code), then to the profile form matching their role. Auth and profile views are listed in `EXEMPT_URL_NAMES`, and static, media, admin, and debug-toolbar paths are skipped. **Add any new URL that must be reachable before the profile is complete to `EXEMPT_URL_NAMES`.**
- The REST API is minimal (legacy from the template; do not extend it): `config/api_router.py` (only `UserViewSet`), DRF token auth, and drf-spectacular docs at `/api/docs/`.

### Payments and donations

`donation` models a donation. `payments.services.PaymentService` creates and transitions `Payment` records (django-money `Money` amounts). Provider integrations live in `payments/providers/{stripe,flutterwave}.py`, and webhook handlers are in `payments/webhooks.py`. Those webhook handlers are not yet wired into `config/urls.py`.

### Frontend / design system

- Server-rendered Django templates styled with Tailwind v4. Design tokens (colors, fonts, radii such as `rounded-control`) are defined in the `@theme` block of `stagelink/static/css/input.css`. Use these tokens (`bg-primary`, `text-text-muted`, `bg-surface`, `border-border`, …) instead of raw colors. Fonts: Inter (body) and Fraunces (display), self-hosted.
- Reusable UI components are include-based templates in `stagelink/core/templates/components/` (button, input, badge, status_badge, offer_card, otp_input, notification_toast, search_bar, donation_widget). Each one documents its variables in a `{% comment %}` header. Use them with `{% include "components/<name>.html" with ... %}`. Matching JS lives in `stagelink/static/js/components/`.
- Icons: `{% load stagelink_icons %}{% icon "name" size="size-5" label="..." %}` inlines local Tabler SVGs from `static/icons/tabler/`. A new icon must be both copied there **and** added to `ALLOWED_ICONS` in `core/templatetags/stagelink_icons.py`, or it silently renders nothing.
- Project templates live in `stagelink/templates/` (`base.html`, `dashboard/`, `home/`, `users/`, `emails/`, `errors/`).
