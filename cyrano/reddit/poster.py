"""Reddit reply poster using PRAW.

Requires a 'script' type app at https://www.reddit.com/prefs/apps
with REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD in .env.
"""

import logging
import time

import praw
from praw.exceptions import RedditAPIException

from cyrano.config import (
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
    REDDIT_USERNAME, REDDIT_PASSWORD,
)

logger = logging.getLogger(__name__)

# Minimum seconds between posts to respect Reddit rate limits
MIN_POST_INTERVAL = 120

_last_post_time: float = 0.0


class RedditPoster:
    """Posts approved replies to Reddit via PRAW."""

    def __init__(self):
        if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD]):
            raise RuntimeError(
                "Reddit credentials not configured. "
                "Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, "
                "REDDIT_USERNAME, REDDIT_PASSWORD in .env"
            )
        self._reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD,
            user_agent="Cyrano/0.1 (value-first reply assistant; human-approved)",
        )

    def _rate_limit(self):
        """Enforce minimum gap between posts."""
        global _last_post_time
        elapsed = time.time() - _last_post_time
        if elapsed < MIN_POST_INTERVAL:
            wait = MIN_POST_INTERVAL - elapsed
            logger.info("Rate limiting: waiting %.0fs before posting", wait)
            time.sleep(wait)

    def post_comment(self, post_url: str, text: str) -> str:
        """Post a top-level comment on a Reddit post.

        Args:
            post_url: Full URL of the Reddit post.
            text: Comment body text.

        Returns:
            Full URL of the posted comment.

        Raises:
            RedditAPIException: If Reddit rejects the post.
            RuntimeError: If the post is locked/archived.
        """
        global _last_post_time
        self._rate_limit()

        submission = self._reddit.submission(url=post_url)

        if submission.locked:
            raise RuntimeError(f"Post is locked: {post_url}")
        if submission.archived:
            raise RuntimeError(f"Post is archived: {post_url}")

        comment = submission.reply(text)
        _last_post_time = time.time()

        comment_url = f"https://reddit.com{comment.permalink}"
        logger.info("Posted comment: %s", comment_url)
        return comment_url

    def reply_to_comment(self, comment_id: str, text: str) -> str:
        """Reply to a specific comment.

        Args:
            comment_id: Reddit comment ID (without t1_ prefix).
            text: Reply body text.

        Returns:
            Full URL of the posted reply.
        """
        global _last_post_time
        self._rate_limit()

        comment = self._reddit.comment(comment_id)
        reply = comment.reply(text)
        _last_post_time = time.time()

        reply_url = f"https://reddit.com{reply.permalink}"
        logger.info("Posted reply to comment %s: %s", comment_id, reply_url)
        return reply_url
