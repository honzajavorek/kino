"""CSFD's anti-bot challenge, kept out of the rest of the codebase.

CSFD walls ordinary clients behind Anubis, a JS proof-of-work challenge, but
lets Telegram's link-preview crawler through without one. Fetching as that
crawler over plain HTTP gets the real pages with no browser at all. If CSFD
ever closes that gap, see the git history for the Camoufox-based approach.
"""

from datetime import timedelta
from typing import Any

from crawlee.crawlers import BeautifulSoupCrawler, HttpCrawlingContext
from crawlee.http_clients import ImpitHttpClient


TELEGRAM_USER_AGENT = "TelegramBot (like TwitterBot)"

CHALLENGE_MARKER = b'<script id="anubis_challenge"'


class ChallengeError(RuntimeError):
    pass


def get_csfd_crawler(**kwargs: Any) -> BeautifulSoupCrawler:
    """A BeautifulSoupCrawler that fetches as TelegramBot and fails any
    request CSFD answers with a challenge instead of the real page. Takes the
    same keyword arguments as BeautifulSoupCrawler.
    """
    kwargs.setdefault("http_client", get_http_client())
    kwargs.setdefault("parser", "html.parser")
    crawler = BeautifulSoupCrawler(**kwargs)

    @crawler.post_navigation_hook
    async def _hook(context: HttpCrawlingContext) -> None:
        raise_if_challenge(context.request.url, await context.http_response.read())

    return crawler


async def fetch_html(url: str, timeout: timedelta | None = None) -> str:
    """Fetch a page's HTML as TelegramBot, for one-off fetches outside crawlee."""
    response = await get_http_client().send_request(url, timeout=timeout)
    body = await response.read()
    raise_if_challenge(url, body)
    return body.decode()


def get_http_client() -> ImpitHttpClient:
    # browser=None: impersonating Firefox would send headers that contradict
    # the TelegramBot User-Agent
    return ImpitHttpClient(browser=None, headers={"User-Agent": TELEGRAM_USER_AGENT})


def raise_if_challenge(url: str, body: bytes) -> None:
    if CHALLENGE_MARKER in body:
        raise ChallengeError(f"CSFD showed an anti-bot challenge for {url}")
