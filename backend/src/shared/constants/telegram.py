"""
Shared Telegram bot constants (SoT for backend).

WHY this module exists:
- Bot polling, handlers, rate limit, and send_alert_fresh must use the same
  limits, timeouts, and API contract
- Single source of truth: no inline magic numbers in bot.py or handlers
- Reusable from any BE code (workers, API, tests)

@see CODING_STANDARDS.md §12 (Constants and Magic Numbers)
"""

from __future__ import annotations

# -----------------------------------------------------------------------------
# Polling resilience (bot.py)
# -----------------------------------------------------------------------------

# Max restarts when the polling loop exits unexpectedly (e.g. after first update).
# Prevents infinite restart loops; logs and gives up after this many.
TELEGRAM_POLLING_RESTART_LIMIT = 5
# Delay in seconds before scheduling a polling restart after exit.
TELEGRAM_POLLING_RESTART_DELAY_SEC = 2.0

# Startup phase: max retries for initial bot.me() / connection (DNS, etc.).
TELEGRAM_POLLING_STARTUP_MAX_RETRIES = 5
# Startup phase: base delay in seconds for exponential backoff between retries.
TELEGRAM_POLLING_STARTUP_BASE_DELAY_SEC = 2.0
# Shutdown: how long TelegramBot.stop() waits for aiogram's own stop_polling (it cancels AND awaits its inner
# _polling task) before falling back to cancelling the outer polling task (UNCLOSED-AIOHTTP, 2026-10-17).
TELEGRAM_STOP_POLLING_TIMEOUT_SEC = 5.0

# The logger aiogram's polling loop reports through (aiogram.loggers.dispatcher).
TELEGRAM_AIOGRAM_DISPATCHER_LOGGER_NAME = "aiogram.dispatcher"

# Exception class name aiogram prints when a second client polls the same bot token.
TELEGRAM_CONFLICT_ERROR_NAME = "TelegramConflictError"

# How long a burst of poller conflicts is read as a deploy ROLLOVER rather than a second poller.
# MEASURED (TGCONFLICT-1, three prod deploys, 2026-09-21): Railway runs the old and new `pulsai`
# containers side by side for ~10-11s before SIGTERM'ing the old one. 30s is ~3x that overlap, and
# aiogram retries a failed poll every <= 5s, so a genuine second poller never leaves a gap this long
# and is still logged as an ERROR once its burst outlives the window.
TELEGRAM_ROLLOVER_CONFLICT_GRACE_SEC = 30.0

# Appended to a conflict logged inside the rollover window, so a reader sees WHY it is a warning.
TELEGRAM_ROLLOVER_CONFLICT_NOTE = "expected during a deploy rollover: the previous container is still polling"

# -----------------------------------------------------------------------------
# Telegram HTTP API (send_alert_fresh)
# -----------------------------------------------------------------------------

TELEGRAM_API_BASE_URL = "https://api.telegram.org"
TELEGRAM_API_SEND_MESSAGE_PATH = "sendMessage"
# Timeout in seconds for sendMessage HTTP request (Celery/workers).
TELEGRAM_SEND_MESSAGE_TIMEOUT_SEC = 10.0
# Parse mode for message text (Markdown).
TELEGRAM_PARSE_MODE_MARKDOWN = "Markdown"

# Telegram Bot API hard limit on sendMessage ``text`` length (platform constant, not tunable).
# https://core.telegram.org/bots/api#sendmessage
TELEGRAM_MESSAGE_MAX_CHARS = 4096

# Special characters that Telegram's LEGACY "Markdown" parse_mode (TELEGRAM_PARSE_MODE_MARKDOWN)
# treats as formatting delimiters: ``_`` italics, ``*`` bold, `` ` `` code, ``[`` link start.
# Dynamic/untrusted text (e.g. RSS headline titles) embedded in a Markdown message must escape
# these or Telegram returns 400 "can't parse entities" for an unmatched delimiter.
TELEGRAM_LEGACY_MARKDOWN_SPECIAL_CHARS = "_*`["

# Suffix appended when dynamic text is truncated to fit a Telegram length budget.
TELEGRAM_MESSAGE_TRUNCATION_SUFFIX = "…"

# What sendMessage's 400 body says when the parse_mode markup is invalid (lower-cased match).
TELEGRAM_UNPARSEABLE_MARKUP_PHRASE = "can't parse entities"

# -----------------------------------------------------------------------------
# Handlers: rate limits and timeouts
# -----------------------------------------------------------------------------

# Max /explain requests per minute per user (AI cost).
TELEGRAM_EXPLAIN_RATE_LIMIT_PER_MINUTE = 5
# Max other commands per minute per user.
TELEGRAM_GENERAL_RATE_LIMIT_PER_MINUTE = 20
# Max seconds for AI explain so polling can process next command.
TELEGRAM_EXPLAIN_TIMEOUT_SECONDS = 90

# Prefix for inline button callback_data on signal alerts (``e:<uuid>``).
# Must stay short: Telegram callback_data max length is 64 bytes.
TELEGRAM_CALLBACK_DATA_MAX_BYTES = 64
TELEGRAM_EXPLAIN_CALLBACK_PREFIX = "e:"

__all__ = [
    "TELEGRAM_AIOGRAM_DISPATCHER_LOGGER_NAME",
    "TELEGRAM_API_BASE_URL",
    "TELEGRAM_API_SEND_MESSAGE_PATH",
    "TELEGRAM_CALLBACK_DATA_MAX_BYTES",
    "TELEGRAM_CONFLICT_ERROR_NAME",
    "TELEGRAM_EXPLAIN_CALLBACK_PREFIX",
    "TELEGRAM_EXPLAIN_RATE_LIMIT_PER_MINUTE",
    "TELEGRAM_EXPLAIN_TIMEOUT_SECONDS",
    "TELEGRAM_GENERAL_RATE_LIMIT_PER_MINUTE",
    "TELEGRAM_LEGACY_MARKDOWN_SPECIAL_CHARS",
    "TELEGRAM_MESSAGE_MAX_CHARS",
    "TELEGRAM_MESSAGE_TRUNCATION_SUFFIX",
    "TELEGRAM_PARSE_MODE_MARKDOWN",
    "TELEGRAM_POLLING_RESTART_DELAY_SEC",
    "TELEGRAM_POLLING_RESTART_LIMIT",
    "TELEGRAM_POLLING_STARTUP_BASE_DELAY_SEC",
    "TELEGRAM_POLLING_STARTUP_MAX_RETRIES",
    "TELEGRAM_ROLLOVER_CONFLICT_GRACE_SEC",
    "TELEGRAM_ROLLOVER_CONFLICT_NOTE",
    "TELEGRAM_SEND_MESSAGE_TIMEOUT_SEC",
    "TELEGRAM_STOP_POLLING_TIMEOUT_SEC",
    "TELEGRAM_UNPARSEABLE_MARKUP_PHRASE",
]
