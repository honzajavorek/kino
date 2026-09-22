"""CSFD-specific anti-bot handling, kept out of the rest of the codebase.

CSFD walls plain HTTP clients (and even crawlee's impit-backed HTTP crawler)
behind a JS proof-of-work challenge. Camoufox - a real, fingerprint-patched
Firefox build - clears it, but its pages need to sit through the challenge's
client-side hash loop before the real page is there to read. Callers get a
browser/crawler that already does that, so they never see a challenge page.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, override

from camoufox import AsyncNewBrowser
from camoufox.async_api import AsyncCamoufox
from crawlee.browsers import (
    BrowserPool,
    PlaywrightBrowserController,
    PlaywrightBrowserPlugin,
)
from crawlee.crawlers import (
    PlaywrightCrawler,
    PlaywrightPostNavCrawlingContext,
)
from playwright.async_api import Page


CHALLENGE_TITLE = "Making sure you're not a bot!"


async def _wait_out_challenge(page: Page, timeout: float = 60000) -> None:
    """Wait out the challenge page, if one was shown.

    It computes a hash puzzle client-side (visible on the page as
    "Calculating... Speed: NkH/s") before redirecting to the real page; a
    plain page load returns long before that finishes.
    """
    if await page.title() == CHALLENGE_TITLE:
        await page.wait_for_function(
            "(expected) => document.title !== expected",
            arg=CHALLENGE_TITLE,
            timeout=timeout,
        )


class CamoufoxPlugin(PlaywrightBrowserPlugin):
    """A browser plugin that launches Camoufox instead of a stock Playwright
    browser.

    See https://crawlee.dev/python/docs/examples/playwright-crawler-with-camoufox
    """

    @override
    async def new_browser(self) -> PlaywrightBrowserController:
        if not self._playwright:
            raise RuntimeError("Playwright browser plugin is not initialized.")
        return PlaywrightBrowserController(
            browser=await AsyncNewBrowser(
                self._playwright, **self._browser_launch_options
            ),
            max_open_pages_per_browser=1,
            header_generator=None,  # Camoufox generates its own headers
        )


def get_crawler(**kwargs: Any) -> PlaywrightCrawler:
    """A PlaywrightCrawler that runs on Camoufox and waits out CSFD's
    challenge after every navigation, before its request handler sees the
    page. Takes the same keyword arguments as PlaywrightCrawler.
    """
    crawler = PlaywrightCrawler(
        browser_pool=BrowserPool(plugins=[CamoufoxPlugin()]),
        **kwargs,
    )

    @crawler.post_navigation_hook
    async def _hook(context: PlaywrightPostNavCrawlingContext) -> None:
        await _wait_out_challenge(context.page)

    return crawler


class AntibotPage:
    """A Camoufox page whose goto() waits out CSFD's challenge before
    returning, so callers never see a challenge page."""

    def __init__(self, page: Page) -> None:
        self._page = page

    async def goto(self, url: str, **kwargs: Any) -> None:
        await self._page.goto(url, **kwargs)
        await _wait_out_challenge(self._page)

    async def content(self) -> str:
        return await self._page.content()


@asynccontextmanager
async def antibot_page() -> AsyncIterator[AntibotPage]:
    """A single Camoufox page for one-off fetches outside crawlee."""
    async with AsyncCamoufox(headless=True) as browser:
        yield AntibotPage(await browser.new_page())
