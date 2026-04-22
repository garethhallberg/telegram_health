# Personal Telegram Logger and Analysis Assistant — Product Spec

## Overview

Build a small personal system that captures daily health and routine data through Telegram, stores it locally in a predictable folder structure, and uses an LLM only for analysis and summaries.

The core design principle is:

**capture must be deterministic; analysis may be probabilistic.**

That means:

* raw logging should never depend on an LLM making the right tool call
* appending to files must be done by normal application logic
* LLM usage is for classification, summarisation, extraction, calorie estimation, and pattern spotting
* the raw daily log files are the source of truth

This replaces the unreliable Hermes workflow with a simple local app that can later grow into something more sophisticated.

---

## Goals

### Primary goals

1. Capture messages, images, and simple check-ins from Telegram.
2. Store everything locally under a single root folder.
3. Never overwrite log files accidentally.
4. Make the data human-browsable without any database tooling.
5. Support later analysis with Mistral or another model.
6. Keep v1 simple enough to build quickly with Codex.

### Non-goals for v1

1. No MCP server.
2. No SQL database.
3. No vector database.
4. No autonomous agent behaviour.
5. No complex workflow engine.
6. No real-time conversational experience.
7. No attempt to infer exact calories from photos alone.

---

## User context and intended use

The user will interact with the system asynchronously through Telegram.

Typical inputs:

* meal descriptions
* ingredient-based cooking notes
* workout notes
* Garmin screenshots
* bedtime check-ins such as “no booze tonight”
* occasional free-form notes about recovery, soreness, steps, or sleep

The user does not care about instant response speed.
The user wants reliability, persistence, and useful summaries.
The user cooks from scratch, so ingredient-based calorie estimation is much more valuable than generic food database matching.

---

## Core principles

### 1. Raw data first

Every message or file received should be stored before any analysis happens.

### 2. Append-only logging

For daily text logs, new entries are appended. Existing content is never overwritten.

### 3. Filesystem is the source of truth

For month one, folders and text files are the primary datastore.

### 4. Analysis is separate from capture

Capture should succeed even if LLM analysis fails.

### 5. Keep the system inspectable

A human should be able to open Finder or a terminal and understand what happened.

---

## High-level architecture

### Components

1. **Telegram bot interface**

   * receives user messages, images, and other attachments
   * sends simple acknowledgements
   * optionally sends scheduled reminders

2. **Local application service**

   * runs on the user’s Mac
   * processes Telegram updates
   * routes content to the correct daily files
   * stores images and attachments
   * triggers optional analysis jobs

3. **Filesystem datastore**

   * stores all raw logs, images, and generated summaries

4. **Optional LLM analysis layer**

   * calls Mistral API or another provider
   * generates summaries, calorie estimates, extraction results, and pattern reviews
   * must not be required for basic logging

---

## Root folder structure

Use this root directory:

`/Users/garethhallberg/hermes-life-admin`

### Folder layout

```text
/Users/garethhallberg/hermes-life-admin
  /data
    /daily
      /YYYY-MM-DD
        meals.txt
        training.txt
        sleep.txt
        habits.txt
        notes.txt
        summary.txt
        /images
        /attachments
    /weekly_summaries
      /YYYY-Www-summary.txt
    /monthly_reviews
      /YYYY-MM-review.txt
  /inbox
    /unclassified
  /logs
  /config
  /scripts
  /prompts
```

### Notes

* `data/daily/YYYY-MM-DD/` is the centre of gravity.
* Every day gets its own folder.
* Text files should remain plain UTF-8 text.
* `summary.txt` is optional and generated later.
* `images/` holds meal photos, Garmin screenshots, and similar.
* `attachments/` holds any non-image files.

---

## Daily files

### `meals.txt`

Append-only log of food and drink messages.

Examples:

* `08:15 Breakfast: three scrambled eggs, toast, fresh tomatoes and cucumber`
* `19:05 Dinner: lentil dal with rice and spicy cauliflower`
* `21:40 No booze tonight`

### `training.txt`

Workout plans, workout completions, and gym notes.

Examples:

* `10:30 Reminder sent: leg day by midday`
* `13:10 Completed: safety bar squats, pendulum squats, leg curls`
* `13:15 Note: legs fried after first two main lifts`

### `sleep.txt`

Sleep notes, Garmin interpretations, and recovery comments.

Examples:

* `07:10 Garmin screenshot received: images/garmin_sleep_01.png`
* `07:11 User note: body battery better than usual`

### `habits.txt`

Boolean-style or short-form daily habits.

Examples:

* `21:45 No booze: yes`
* `18:20 Steps target: reached`

### `notes.txt`

Fallback for anything that does not fit clearly elsewhere.

Examples:

* `17:00 Felt tired after yesterday's leg day`
* `17:30 Skipped light conditioning today`

### `summary.txt`

Generated by the analysis layer.
Should never be treated as source data.

---

## Input types

### 1. Plain text message

Examples:

* `Breakfast: three scrambled eggs, toast, fresh tomatoes and cucumber`
* `No booze tonight`
* `Leg day done. Safety bar squats and pendulum squats only`

### 2. Meal with ingredient detail

Examples:

* `Made lentil dal with 150g dried red lentils, 750ml water, one medium onion, four cloves of garlic, 150g Greek yoghurt. Served with 200g rice. I ate one third.`

### 3. Image

Examples:

* Garmin screenshot
* meal photo

### 4. Mixed input

Image plus caption.

### 5. Explicit command

Examples:

* `summarise today`
* `estimate calories for this meal`
* `weekly review`

---

## Message routing rules

### Deterministic routing first

Use simple rule-based routing before involving an LLM.

#### Route to `meals.txt` if message contains cues like:

* breakfast
* lunch
* dinner
* snack
* ate
* drank
* yoghurt
* rice
* lentils
* eggs
* toast
* dal
* curry
* no booze
* alcohol

#### Route to `training.txt` if message contains cues like:

* gym
* workout
* leg day
* squats
* curls
* press
* deadlift
* pull-up
* completed
* session

#### Route to `sleep.txt` if message contains cues like:

* sleep
* woke up
* body battery
* Garmin
* recovery
* fatigue

#### Route to `habits.txt` if message contains cues like:

* no booze
* steps
* walk
* target met
* habit

#### Otherwise route to `notes.txt`

### Important rule

A single message may be copied to more than one file only if this is intentional and clearly beneficial. Default behaviour should be one primary destination.

---

## File writing rules

1. Always create the day folder if missing.
2. Always append to the correct text file.
3. Never overwrite an existing log file.
4. Every log entry must include a timestamp in `HH:MM` 24-hour format.
5. If the message includes multiple lines, preserve the content sensibly.
6. If the input is an image, save the image first, then append a reference line to the relevant text file.
7. If anything fails, log the raw message to `notes.txt` and record an application log entry.

---

## Image handling

### For any image received

1. Save the original file locally.
2. Generate a deterministic filename.
3. Place it in the relevant day folder under `images/`.
4. Append a text reference to the associated daily file.

### Example filenames

* `garmin_sleep_01.jpg`
* `garmin_body_battery_01.png`
* `meal_dinner_01.jpg`
* `meal_lunch_02.jpg`

### V1 behaviour

For v1, do not attempt advanced OCR or calorie estimation automatically.
Just store the image and a short reference.

### V2 behaviour

Optionally run image analysis asynchronously.
Examples:

* identify that a screenshot is a Garmin sleep panel
* identify that a meal photo appears to be dal and rice
* extract visible metrics where legible

---

## Telegram bot behaviour

### Inbound behaviour

On receiving a message:

1. persist raw input
2. classify it
3. append to the relevant file
4. send a short acknowledgement

### Acknowledgement style

Keep responses short and functional.
Examples:

* `Logged to meals.`
* `Saved Garmin screenshot.`
* `Logged to training.`
* `Saved to notes.`

Do not send long wellness essays by default.

### Outbound scheduled messages

The bot should support scheduled prompts such as:

* morning workout nudge
* evening food capture reminder
* pre-bed no-booze check
* weekly review prompt

---

## Scheduled jobs

### 1. Workout nudge

Schedule: configurable, e.g. 10:30 on workout days.

Example message:

* `Leg day. Aim to get there by midday. Safety bar squats, pendulum squats, leg curls.`

### 2. Evening capture prompt

Schedule: configurable, e.g. 19:30 daily.

Example message:

* `What have you eaten today? Add any final meals or snacks.`

### 3. Pre-bed check

Schedule: configurable, e.g. 21:30 daily.

Example message:

* `Quick check: any more food or drink tonight, and was it a no-booze day?`

### 4. Weekly review prompt or auto-summary

Schedule: configurable, e.g. Sunday 18:00.

Example message:

* `Reviewing the week now.`

---

## Analysis layer

The analysis layer is optional and separate.
It should read from files and write outputs back to files.
It should never mutate raw logs.

### V1 analysis features

1. `summarise today`

   * read today’s files
   * create or update `summary.txt`

2. `weekly review`

   * read last 7 days
   * write `/data/weekly_summaries/YYYY-Www-summary.txt`

3. `estimate calories`

   * for ingredient-based meal messages, estimate calories as a range
   * store result in `summary.txt` or a derived analysis section, not by rewriting the raw meal entry

### V2 analysis features

1. image-based meal estimation
2. Garmin screenshot metric extraction
3. confidence scoring
4. pattern spotting across multiple weeks
5. simple trend reports for alcohol, sleep, training consistency, and food quality

---

## Calorie estimation design

### Guiding principle

Ingredient-plus-portion input is much more useful than photo-only input.

### Good input example

`Made lentil dal with 150g dried red lentils, 750ml water, one medium onion, four cloves of garlic, 150g 10% Greek yoghurt. Served with 200g rice cooked with 400ml water. I ate one third.`

### Expected behaviour

1. Preserve the original message in `meals.txt`.
2. Optionally generate an estimate asynchronously.
3. Return a calorie range, not fake precision.
4. Note uncertainty drivers such as oil quantity, yoghurt fat percentage, or portion ambiguity.

### Example response style

* `Estimated portion: 650–730 kcal`
* `Confidence: medium-high`
* `Main uncertainty: oil quantity`

### Important rule

Never rewrite the raw meal entry with inferred values.
Derived estimates must be stored separately.

---

## Analysis prompt style

The assistant’s tone should be:

* practical
* understated
* not preachy
* not American self-help style
* concise by default

Examples of acceptable tone:

* `Logged.`
* `Estimated portion: around 700 kcal, mostly dependent on oil.`
* `Sleep looked better than usual. No booze may be contributing.`

Examples to avoid:

* motivational speeches
* wellness sermonising
* unsolicited meal optimisation essays
* exaggerated enthusiasm

---

## Configurability

The system should make the following configurable:

1. Telegram bot token
2. allowed chat ID(s)
3. root data directory
4. timezone
5. reminder times
6. workout-day schedule
7. LLM provider settings for analysis
8. whether image analysis is enabled
9. whether calorie estimation is enabled

Use environment variables and/or a small config file.

---

## Security and privacy

1. Restrict the Telegram bot to the user’s chat ID.
2. Store raw data locally.
3. Keep API keys out of code.
4. Use environment variables for secrets.
5. Make cloud LLM use optional and limited to analysis tasks.
6. Do not expose raw logs externally unless explicitly requested.

---

## Suggested technology stack

This is flexible, but a sensible default would be:

* Python 3.11+
* `python-telegram-bot` for Telegram integration
* standard library for filesystem operations
* `APScheduler` or cron for scheduled jobs
* optional `httpx` or official SDK for Mistral API calls
* simple `.env` file for secrets

No database is required for v1.

---

## Main application flows

### Flow 1: Log a meal

1. Telegram bot receives text message.
2. Application timestamps it.
3. Application classifies it as meal-related.
4. Application appends line to today’s `meals.txt`.
5. Bot replies `Logged to meals.`

### Flow 2: Save a Garmin screenshot

1. Telegram bot receives image.
2. Application stores image under today’s `images/`.
3. Application appends reference line to `sleep.txt`.
4. Bot replies `Saved Garmin screenshot.`

### Flow 3: Generate daily summary

1. User sends `summarise today`.
2. Application reads today’s log files.
3. Application calls analysis model.
4. Application writes result to `summary.txt`.
5. Bot returns short summary or confirmation.

### Flow 4: Weekly review

1. Scheduled job runs on Sunday.
2. Application reads last 7 days’ daily files.
3. Application calls analysis model.
4. Application writes weekly summary file.
5. Bot sends a compact weekly recap.

---

## Failure handling

### Logging failure

If classification fails:

* append raw input to `notes.txt`
* write application error log
* reply `Saved to notes.`

### Image save failure

If image download fails:

* record a note in `notes.txt`
* write application error log
* reply with a short failure message

### LLM failure

If analysis fails:

* raw logging must still succeed
* write failure to application log
* optionally tell user `Log saved. Analysis unavailable right now.`

---

## Observability

The app should log:

* incoming Telegram update ID
* message type
* chosen destination file
* whether file append succeeded
* whether image save succeeded
* whether analysis job succeeded
* any exception details

Application logs should go in:

`/Users/garethhallberg/hermes-life-admin/logs/`

---

## Minimum viable version

### Must-have for v1

1. Telegram bot receives text messages.
2. Bot appends messages to the correct daily text file.
3. Bot stores images under the correct day folder.
4. Bot sends short acknowledgements.
5. Daily folders are created automatically.
6. Logging never overwrites existing content.

### Nice-to-have for v1

1. manual `summarise today`
2. pre-bed reminder
3. workout reminder
4. simple keyword-based routing improvements

### Defer to v2

1. image calorie estimation
2. OCR and metric extraction from Garmin screenshots
3. structured JSON or DB layer
4. weekly trend charts
5. rich admin UI

---

## Future evolution

### Phase 2

* introduce derived JSON summaries per day
* add better calorie estimation for ingredient-based meals
* add image interpretation as background analysis
* add weekly and monthly review generation

### Phase 3

* add a document store or SQL layer if patterns justify it
* optionally expose an MCP server for querying logs
* support text-to-SQL or natural-language querying over accumulated data

### Principle for later phases

Do not replace raw text logs as source of truth.
Any structured store should be derived from those logs, not the other way around.

---

## Acceptance criteria

The build is successful if all of the following are true:

1. Sending a Telegram text message results in an appended line in the correct daily file.
2. Existing file contents are preserved.
3. Sending multiple meal messages in one day produces multiple lines in `meals.txt`.
4. Sending an image stores the image under the current day folder.
5. The bot acknowledges each successful save briefly.
6. The system works without the LLM configured.
7. Optional analysis can be added without affecting capture reliability.

---

## Build guidance for Codex

Prioritise the following order:

1. local folder creation
2. safe append function
3. Telegram webhook or polling bot
4. simple keyword routing
5. image download and storage
6. acknowledgements
7. manual summary command
8. scheduled reminders
9. optional Mistral integration for analysis

The first milestone should be a fully working logger with no LLM dependency.

The second milestone should add summaries.

The third milestone should add calorie estimation and pattern spotting.
