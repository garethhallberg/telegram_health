from __future__ import annotations

import logging
from datetime import time, tzinfo

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from hermes_life_admin.analysis import DisabledWeeklyAnalysisAgent, MistralWeeklyAnalysisAgent
from hermes_life_admin.classifier import DisabledClassificationAgent, MistralClassificationAgent
from hermes_life_admin.config import AppConfig
from hermes_life_admin.logger_service import LoggerService
from hermes_life_admin.storage import DailyStorage


LOGGER = logging.getLogger(__name__)


def build_application(config: AppConfig) -> Application:
    storage = DailyStorage(
        root_dir=config.root_dir,
        log_script=config.log_script,
        timezone=config.timezone,
    )
    classification_agent = (
        MistralClassificationAgent(
            api_key=config.mistral_api_key,
            text_model=config.mistral_text_model,
            vision_model=config.mistral_vision_model,
        )
        if config.mistral_api_key
        else DisabledClassificationAgent()
    )
    analysis_agent = (
        MistralWeeklyAnalysisAgent(
            api_key=config.mistral_api_key,
            model=config.mistral_analysis_model,
        )
        if config.mistral_api_key
        else DisabledWeeklyAnalysisAgent()
    )
    service = LoggerService(storage, classification_agent, analysis_agent)

    application = Application.builder().token(config.telegram_bot_token).build()
    application.bot_data["config"] = config
    application.bot_data["logger_service"] = service

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    schedule_reminders(application, config)
    return application


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update, context):
        return
    await update.effective_message.reply_text("Ready.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update, context):
        return

    service: LoggerService = context.application.bot_data["logger_service"]
    result = service.log_text(update.effective_message.text or "")
    await update.effective_message.reply_text(result.acknowledgement)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update, context):
        return

    message = update.effective_message
    photo = message.photo[-1]
    telegram_file = await photo.get_file()
    content = bytes(await telegram_file.download_as_bytearray())

    service: LoggerService = context.application.bot_data["logger_service"]
    result = service.log_image(
        content=content,
        caption=message.caption,
        original_name=f"{photo.file_unique_id}.jpg",
        mime_type="image/jpeg",
    )
    await message.reply_text(result.acknowledgement)


def schedule_reminders(application: Application, config: AppConfig) -> None:
    job_queue = application.job_queue
    if job_queue is None:
        LOGGER.warning("Job queue is unavailable; scheduled reminders are disabled.")
        return

    chat_ids = tuple(config.allowed_chat_ids)
    for chat_id in chat_ids:
        job_queue.run_daily(
            send_reminder,
            time=_parse_time(config.workout_reminder_time, config.timezone),
            days=_telegram_days(config.workout_days),
            data={"chat_id": chat_id, "text": "Leg day. Aim to get there by midday."},
            name=f"workout-reminder-{chat_id}",
        )
        job_queue.run_daily(
            send_reminder,
            time=_parse_time(config.evening_capture_time, config.timezone),
            data={"chat_id": chat_id, "text": "What have you eaten today? Add any final meals or snacks."},
            name=f"evening-capture-{chat_id}",
        )
        job_queue.run_daily(
            send_reminder,
            time=_parse_time(config.pre_bed_check_time, config.timezone),
            data={
                "chat_id": chat_id,
                "text": "Quick check: any more food or drink tonight, and was it a no-booze day?",
            },
            name=f"pre-bed-check-{chat_id}",
        )
        job_queue.run_daily(
            run_weekly_review,
            time=_parse_time(config.weekly_review_time, config.timezone),
            days=(0,),
            data={"chat_id": chat_id},
            name=f"weekly-review-{chat_id}",
        )


async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    await context.bot.send_message(chat_id=data["chat_id"], text=data["text"])


async def run_weekly_review(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    chat_id = data["chat_id"]
    service: LoggerService = context.application.bot_data["logger_service"]
    await context.bot.send_message(chat_id=chat_id, text="Reviewing the week now...")
    summary = service.weekly_review()
    await context.bot.send_message(chat_id=chat_id, text=summary)


def _allowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    config: AppConfig = context.application.bot_data["config"]
    chat = update.effective_chat
    if chat is None or chat.id not in config.allowed_chat_ids:
        LOGGER.warning("Ignoring update from unauthorized chat ID %s", chat.id if chat else None)
        return False
    return True


def _parse_time(value: str, timezone: tzinfo) -> time:
    hour, minute = value.split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute), tzinfo=timezone)


def _telegram_days(days: tuple[str, ...]) -> tuple[int, ...]:
    mapping = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
    return tuple(mapping[day] for day in days if day in mapping)
