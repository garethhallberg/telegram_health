# Hermes Life Admin

Personal Telegram logger for append-only daily files.

## Setup

Install dependencies with `uv`:

```bash
uv sync
```

Edit `.env` with your real Telegram bot token, allowed chat ID, and Mistral API key. For image categorization, use a vision-capable model such as `mistral-small-2506` for `MISTRAL_VISION_MODEL`.

## Run

```bash
uv run hermes-life-admin
```

The bot accepts text messages and photos from configured chat IDs only. A small Mistral-backed classification agent chooses one or more destinations for each message. Text log entries are appended through `bin/log_entry.sh` into:

- `data/daily/YYYY-MM-DD/meals.txt`
- `data/daily/YYYY-MM-DD/training.txt`
- `data/daily/YYYY-MM-DD/sleep.txt`
- `data/daily/YYYY-MM-DD/habits.txt`
- `data/daily/YYYY-MM-DD/notes.txt`

Photos are saved under `data/daily/YYYY-MM-DD/images/`, classified by the Mistral-backed agent using the image content plus any caption, then a reference line is appended through `bin/log_entry.sh`.

If classification fails or no Mistral API key is configured, the message is logged to `notes.txt`, a warning is printed to the console, and details are appended to `logs/error.log`.

Analysis commands such as `summarise today`, `weekly review`, and `estimate calories` are currently acknowledged as not implemented and logged to `notes.txt`.

## Test

```bash
uv run pytest
```
