# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the bot
uv run hermes-life-admin

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_logger_service.py

# Run a single test by name
uv run pytest tests/test_logger_service.py::test_log_text_appends_to_each_routed_file
```

The project uses `uv` for dependency management. Do not use `pip` directly.

## Architecture

The bot is a personal Telegram logger that captures health/routine data and appends it to local daily text files. The central design constraint is: **capture must be deterministic; analysis may be probabilistic.** Logging must never fail silently or depend on LLM availability.

### Request flow

```
Telegram message
  → bot.py (handle_text / handle_photo)
    → LoggerService (logger_service.py)
      → routing.py (is_analysis_command / route_text)
      → ClassificationAgent (classifier.py) — calls Mistral API
      → DailyStorage (storage.py) — appends via bin/log_entry.sh
```

### Key modules

- **`bot.py`** — Telegram handler wiring; builds the `Application`, attaches handlers, schedules daily reminder jobs via the job queue.
- **`config.py`** — All config loaded from `.env` via `AppConfig.from_env()`. Hardcoded `ROOT_DIR` fallback points to this repo.
- **`logger_service.py`** — Orchestrates the capture pipeline. On `ClassificationError`, falls back to `notes.txt` and writes to `logs/error.log`. Always stores images before classifying.
- **`routing.py`** — Defines the five `Destination` enum values (`meals`, `training`, `sleep`, `habits`, `notes`) and keyword cue sets. `route_text` delegates entirely to the classification agent; the cue sets are there for reference/future use.
- **`classifier.py`** — Two implementations of the `ClassificationAgent` protocol: `MistralClassificationAgent` (calls Mistral) and `DisabledClassificationAgent` (raises `ClassificationError`). If `MISTRAL_API_KEY` is missing or starts with `dummy-`, the disabled agent is used.
- **`storage.py`** — `DailyStorage` writes log entries by shelling out to `bin/log_entry.sh` (never writes directly). Images go under `data/daily/YYYY-MM-DD/images/` with sequential filenames like `garmin_sleep_01.jpg`. Error logs go to `logs/error.log`.

### Data layout

```
data/daily/YYYY-MM-DD/
  meals.txt
  training.txt
  sleep.txt
  habits.txt
  notes.txt
  images/
logs/
  error.log
```

All log entries are append-only. **Never write directly to log files** — always go through `bin/log_entry.sh`.

### Classification

Text is classified by the Mistral API returning `{"destinations": [...], "reason": "..."}`. Images use a vision model returning `{"destinations": [...], "image_kind": "...", "note": "..."}`. Both fall back to `notes` on any error.

### Scheduled reminders

`bot.py::schedule_reminders` registers four daily jobs via the telegram job queue: workout nudge (configurable days), evening capture prompt, pre-bed check, and weekly review (Sundays). Times are configurable via env vars.

## Environment variables

Required:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_IDS` — comma-separated chat IDs

Optional (with defaults):
- `MISTRAL_API_KEY` — omit or prefix `dummy-` to disable classification
- `MISTRAL_TEXT_MODEL` — defaults to `mistral-small-latest`
- `MISTRAL_VISION_MODEL` — defaults to `mistral-small-2506`
- `HERMES_TIMEZONE` — defaults to `Europe/London`
- `WORKOUT_REMINDER_TIME`, `EVENING_CAPTURE_TIME`, `PRE_BED_CHECK_TIME`, `WEEKLY_REVIEW_TIME`
- `WORKOUT_DAYS` — comma-separated e.g. `mon,wed,fri`

## Testing approach

Tests use `tmp_path` fixtures with a real shell script (copied from `bin/log_entry.sh`) instead of mocking `DailyStorage`. The `ClassificationAgent` protocol is satisfied by `FakeClassificationAgent` or `FailingClassificationAgent` inline classes. Do not mock the storage layer.

## AGENTS.md

`AGENTS.md` defines rules for Claude/Codex acting as a logging assistant directly (outside the bot). It mandates using `bin/log_entry.sh` for all log writes — never write log files directly, never overwrite existing content.
