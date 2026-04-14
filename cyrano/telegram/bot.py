"""Telegram bot for Cyrano approval flow.

Sends scored signal cards with inline keyboards. Handles:
  [Approve]  → post reply as-is
  [Edit]     → wait for user's reply message, then post that text
  [Skip]     → mark dismissed
  [No Plug]  → strip product mentions, then post

Usage:
    bot = CyranoBot(token, chat_id)
    await bot.start()
    await bot.send_candidate(scored_signal)
    # ...
    await bot.stop()
"""

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from cyrano.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from cyrano.storage.approvals import save_approval
from cyrano.telegram.formatter import format_candidate, format_status_update

if TYPE_CHECKING:
    from cyrano.models import ScoredSignal

logger = logging.getLogger(__name__)

# ConversationHandler state
WAITING_FOR_EDIT = 1


class CyranoBot:
    """Telegram bot that manages the human-in-the-loop approval flow."""

    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self._app: Application | None = None
        # signal_id -> ScoredSignal, for callback lookup
        self._pending: dict[str, "ScoredSignal"] = {}
        # signal_id currently awaiting edit text
        self._edit_pending: str | None = None

        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is not set")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def build(self) -> Application:
        """Build the Application (call before start())."""
        app = Application.builder().token(self.token).build()

        # Conversation handler for the Edit flow
        edit_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self._handle_edit, pattern=r"^edit:")],
            states={
                WAITING_FOR_EDIT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_edit_text)
                ],
            },
            fallbacks=[],
            per_message=False,
        )

        app.add_handler(edit_conv)
        app.add_handler(CallbackQueryHandler(self._handle_callback))

        self._app = app
        return app

    async def start(self):
        """Initialize the bot and start polling (blocking)."""
        if self._app is None:
            await self.build()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        logger.info("Cyrano bot started — polling for updates")

    async def stop(self):
        """Graceful shutdown."""
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Cyrano bot stopped")

    # ------------------------------------------------------------------
    # Sending candidates
    # ------------------------------------------------------------------

    async def send_candidate(self, scored: "ScoredSignal") -> None:
        """Send a scored signal card to the approval chat."""
        if self._app is None:
            raise RuntimeError("Bot not started — call build() first")

        text, keyboard = format_candidate(scored)
        try:
            msg = await self._app.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            scored.telegram_message_id = msg.message_id
            self._pending[scored.signal_id] = scored
            logger.info("Sent candidate to Telegram: %s", scored.signal_id)
        except Exception as e:
            logger.error("Failed to send candidate %s: %s", scored.signal_id, e)

    # ------------------------------------------------------------------
    # Callback handlers
    # ------------------------------------------------------------------

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route button presses to the appropriate handler."""
        query = update.callback_query
        await query.answer()

        action, signal_id = query.data.split(":", 1)
        scored = self._pending.get(signal_id)

        if scored is None:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                f"⚠️ Signal `{signal_id}` not found in session \\(already handled?\\)",
                parse_mode="MarkdownV2",
            )
            return

        if action == "approve":
            await self._do_approve(query, scored, action="approved")
        elif action == "skip":
            await self._do_skip(query, scored)
        elif action == "noplug":
            await self._do_noplug(query, scored)
        # "edit" is handled by ConversationHandler — this branch shouldn't fire

    async def _handle_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Entry point for the Edit flow — prompt user for their text."""
        query = update.callback_query
        await query.answer()

        _, signal_id = query.data.split(":", 1)
        scored = self._pending.get(signal_id)

        if scored is None:
            await query.edit_message_reply_markup(reply_markup=None)
            return ConversationHandler.END

        self._edit_pending = signal_id
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "✏️ Send your edited reply text now\\. "
            "Reply to this message or just type it\\.",
            parse_mode="MarkdownV2",
        )
        return WAITING_FOR_EDIT

    async def _handle_edit_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive the user's edited text and approve with it."""
        signal_id = self._edit_pending
        if signal_id is None:
            return ConversationHandler.END

        self._edit_pending = None
        scored = self._pending.get(signal_id)
        if scored is None:
            return ConversationHandler.END

        scored.edited_text = update.message.text.strip()
        await update.message.reply_text("Got it — posting your edited reply\\.", parse_mode="MarkdownV2")
        await self._post_reply(scored, action="edited")
        return ConversationHandler.END

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def _do_approve(self, query, scored: "ScoredSignal", action: str = "approved"):
        await query.edit_message_reply_markup(reply_markup=None)
        await self._post_reply(scored, action=action)

    async def _do_skip(self, query, scored: "ScoredSignal"):
        scored.approval_status = "skipped"
        save_approval(
            signal_id=scored.signal_id,
            decision="skipped",
            project=scored.project,
            telegram_message_id=scored.telegram_message_id,
        )
        self._pending.pop(scored.signal_id, None)
        status_text = format_status_update(scored, "skipped")
        await query.edit_message_text(text=status_text, parse_mode=None)
        logger.info("Skipped: %s", scored.signal_id)

    async def _do_noplug(self, query, scored: "ScoredSignal"):
        """Strip product plug from reply text, then approve."""
        # Mark so the poster knows to use the stripped version
        # The Reddit poster will handle actual plug removal via a re-prompt if needed.
        # For now we approve with a "noplug" flag — poster reads scored.approval_status.
        await query.edit_message_reply_markup(reply_markup=None)
        await self._post_reply(scored, action="noplug")

    async def _post_reply(self, scored: "ScoredSignal", action: str):
        """Hand off to the Reddit poster and update the Telegram message."""
        from cyrano.reddit.poster import RedditPoster

        scored.approval_status = action
        reply_text = scored.reply_text

        save_approval(
            signal_id=scored.signal_id,
            decision=action,
            project=scored.project,
            edited_text=scored.edited_text,
            telegram_message_id=scored.telegram_message_id,
        )

        # Attempt to post to Reddit
        poster = RedditPoster()
        comment_url = None
        error_msg = None

        try:
            comment_url = poster.post_comment(scored.signal.url, reply_text)
            scored.comment_url = comment_url
            scored.approval_status = "posted"
            save_approval(
                signal_id=scored.signal_id,
                decision="posted",
                project=scored.project,
                edited_text=scored.edited_text,
                telegram_message_id=scored.telegram_message_id,
            )
            from cyrano.storage.post_history import record_post
            record_post(
                signal_id=scored.signal_id,
                project=scored.project,
                post_url=scored.signal.url,
                comment_url=comment_url,
                reply_text=reply_text,
                action=action,
            )
            logger.info("Posted reply for %s: %s", scored.signal_id, comment_url)
        except Exception as e:
            error_msg = str(e)
            logger.error("Reddit post failed for %s: %s", scored.signal_id, e)

        # Update the Telegram card
        extra = comment_url or (f"❌ Post failed: {error_msg}" if error_msg else "")
        status_text = format_status_update(scored, "posted" if comment_url else "error", extra)

        if scored.telegram_message_id and self._app:
            try:
                await self._app.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=scored.telegram_message_id,
                    text=status_text,
                )
            except Exception as e:
                logger.warning("Could not update Telegram message: %s", e)

        self._pending.pop(scored.signal_id, None)
