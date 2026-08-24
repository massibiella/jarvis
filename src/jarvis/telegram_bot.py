"""Telegram long-polling interface — lets you text Jarvis from your phone
while it runs on a home PC with no public IP/port-forwarding, since polling
only needs outbound HTTPS to api.telegram.org (no inbound connection).

Started/stopped by server.py's FastAPI lifespan alongside uvicorn, sharing
server.py's single Agent instance and asyncio.Lock — a Telegram message and
an HTTP /chat request are serialized through the same lock, and both see
the same conversation history. Entirely optional: if config.telegram isn't
set, start_telegram_bot() is a no-op and server.py behaves exactly as before.

Uses python-telegram-bot's manual Application lifecycle (initialize/start/
updater.start_polling, and the mirrored shutdown calls) rather than
Application.run_polling(), which owns the event loop itself and blocks —
incompatible with living inside an already-running asyncio app.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes, MessageHandler, filters

from jarvis.agent import Agent
from jarvis.config import JarvisConfig

logger = logging.getLogger(__name__)

_TELEGRAM_MESSAGE_LIMIT = 4096


def _split_for_telegram(text: str, limit: int = _TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Break a reply into <=limit-char chunks, on line boundaries where
    possible, so a long agent reply doesn't get rejected by Telegram."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def _make_handler(agent, lock, allowed_chat_ids: set[int]):
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        message = update.message
        if chat is None or message is None or not message.text:
            return

        if chat.id not in allowed_chat_ids:
            logger.warning("Ignoring Telegram message from unauthorized chat id %s", chat.id)
            return

        try:
            async with lock:
                reply = await agent.step(message.text)
        except Exception:
            logger.exception("Error handling Telegram message")
            reply = "Sorry, something went wrong."

        for chunk in _split_for_telegram(reply):
            await message.reply_text(chunk)

    return handle_message


def build_telegram_app(config: JarvisConfig, agent: Agent, lock) -> Application:
    assert config.telegram is not None
    telegram_config = config.telegram

    application = ApplicationBuilder().token(telegram_config.bot_token).build()
    handler = _make_handler(agent, lock, set(telegram_config.allowed_chat_ids))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler))
    return application


async def start_telegram_bot(config: JarvisConfig, agent: Agent, lock) -> Application | None:
    """No-op (returns None) if config.telegram isn't set — Telegram stays
    fully optional. Otherwise starts long-polling and returns the running
    Application, to be passed to stop_telegram_bot() on shutdown."""
    if config.telegram is None:
        return None

    application = build_telegram_app(config, agent, lock)
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Telegram bot started (long-polling)")
    return application


async def stop_telegram_bot(application: Application | None) -> None:
    if application is None:
        return
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    logger.info("Telegram bot stopped")
