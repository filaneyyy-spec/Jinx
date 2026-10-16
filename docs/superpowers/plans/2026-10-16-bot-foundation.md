# Bot Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a tested Telegram bot foundation that registers users and gates its menu on channel membership.

**Architecture:** aiogram polling bot with isolated configuration, SQLite storage, membership checks and handlers. No sales, VPN provisioning or deployment with unavailable credentials.

**Tech Stack:** Python 3.12, aiogram 3, aiosqlite, pydantic-settings, uv, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-10-16-bot-foundation.md`

## Global Constraints

- Default channel: -1002819525144; tariffs display «—».
- No bot token, server password or runtime database in Git.
- No outgoing user messages until a real bot token is configured for the requested bot.
- Existing isolated cloud checkout is used; no additional worktree.
- Subsequent payments support Stars in Telegram and YooKassa on a separate website. Windows precedes Android.

## Review Focus

- Unknown/failed membership must never grant access (task 2).
- Repeated or concurrent /start must not duplicate users (tasks 1–2).
- Missing token and invalid URL must fail without leaking configuration (tasks 1, 3).
- Group and inline callbacks must not expose a personal menu (task 2).
- Existing webhook or missing channel admin rights must prevent polling without altering remote configuration (task 3).

## Task 1: Configuration and durable users

Files: `config.py`, `storage.py`, `tests/test_config.py`, `tests/test_storage.py` under the package/tests directories.

Interfaces: `Settings` exposes `bot_token`, `channel_id`, `channel_url`, `mini_app_url`, `support_url`, `database_path`; `Database(path)` exposes async `initialize`, `close`, `upsert_user(telegram_id, username, full_name)` and `get_user(telegram_id)` returning a UserRecord or None.

- [x] Write and run failing tests for defaults, secret redaction, HTTPS URL validation, persistent updates and duplicate-user handling.
- [x] Implement the interfaces, atomic SQLite upsert and repeatable schema creation.
- [x] Run the config/storage test files and verify all pass.

## Task 2: Membership and bot flows

Files: `membership.py`, `handlers.py`, `tests/fakes.py`, `tests/test_bot.py`.

Interfaces: `check_membership(bot, channel_id, user_id) -> Membership`; `create_dispatcher(settings, database) -> Dispatcher` consumes task 1 and injects dependencies.

- [x] Write Dispatcher-level tests with a fake external API for /start, registration, join/recheck, denied access, stale membership, restricted status, API failure and group/inline callbacks; duplicate registration is covered by the storage tests.
- [x] Implement membership classification, Russian text, keyboards and private-chat handlers.
- [x] Run the full test suite; verify no payments, invented links or user-supplied identities grant access.

## Task 3: Runtime, documentation and CI

Files: `main.py`, `tests/test_runtime.py`, `.env.example`, `.github/workflows/ci.yml`, `README.md`, `docs/NEXT_STEPS.md`.

Interfaces: CLI `jinx-bot --check` validates local configuration/database without network; `jinx-bot` performs safe Telegram preflight then starts polling.

- [x] Write failing tests for missing token, webhook conflict, channel permissions and successful preflight.
- [x] Implement startup and cleanup; document exact setup and bot permissions, deferred capabilities and secret handling.
- [x] Run all tests, Ruff, local --check, frozen reinstall and wheel build.
- [ ] Request independent review, address material findings, publish code/CI to the authorized Jinx repository and verify the actual CI result where access permits.

## Execution record

The user explicitly requested starting the bot foundation after the broader proposal. Proceed with this narrower deliverable; no further choice of implementation method is needed. Setup-only source protections are superseded by the user's explicit request to build the project.

Independent review found a polling-log credential disclosure path, reproduced with a synthetic token. Added a redacting formatter covering messages, tracebacks and URL-encoded tokens, plus a real Dispatcher polling regression. Runtime resource-cleanup paths were reviewed; they do not yet have direct lifecycle tests. Live Telegram validation remains pending the token and channel rights. The credential-free SSH banner workflow passed on both target servers; no authenticated server session has been opened.
