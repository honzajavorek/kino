"""CSFD's anti-bot challenge, kept out of the rest of the codebase.

CSFD walls plain HTTP clients (and even crawlee's impit-backed HTTP crawler)
behind a JS proof-of-work challenge. Camoufox - a real, fingerprint-patched
Firefox build - clears it, but its pages need to sit through the challenge's
client-side hash loop before the real page is there to read. Callers get a
browser/crawler that already does that, so they never see a challenge page.
"""

from typing import Any, override

from camoufox import AsyncNewBrowser, DefaultAddons
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


# Camoufox bundles uBlock Origin by default. It blocks Anubis's own challenge
# script - served from a path generic filter lists flag as tracking, e.g.
# /.within.website/x/cmd/anubis/... - which strands the browser on the
# challenge page with "Anubis could not load its JavaScript" instead of ever
# solving it. Every Camoufox launch below excludes it.
LAUNCH_OPTIONS: dict[str, Any] = {"exclude_addons": [DefaultAddons.UBO]}

CHALLENGE_TITLE = "Making sure you're not a bot!"

# The title CSFD's anti-bot layer shows when it denies a request outright,
# without offering a challenge to solve. Unlike the challenge, this isn't
# something to wait out - the only known recovery is a fresh browser session.
DENIED_TITLE = "Oh noes!"

FETCH_ATTEMPTS = 3


class DeniedError(RuntimeError):
    pass


async def _pass_challenge(page: Page, timeout: float = 60000) -> None:
    """Wait out the challenge page, if one was shown; raise DeniedError if
    CSFD denied the request outright instead.

    The challenge computes a hash puzzle client-side (visible on the page as
    "Calculating... Speed: NkH/s") before redirecting to the real page; a
    plain page load returns long before that finishes.
    """
    if await page.title() == CHALLENGE_TITLE:
        await page.wait_for_function(
            "(expected) => document.title !== expected",
            arg=CHALLENGE_TITLE,
            timeout=timeout,
        )
    if await page.title() == DENIED_TITLE:
        body = await page.inner_text("body")
        raise DeniedError(body.strip().splitlines()[0] if body.strip() else "denied")


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


def get_csfd_crawler(**kwargs: Any) -> PlaywrightCrawler:
    """A PlaywrightCrawler that runs on Camoufox and waits out CSFD's
    challenge after every navigation, before its request handler sees the
    page. Takes the same keyword arguments as PlaywrightCrawler.
    """
    # CSFD fills in parts of the page (e.g. the country/genre filter select
    # boxes) via a follow-up request after the "load" event Playwright's own
    # default waits for; wait for the network to settle instead, or handlers
    # see a page that's there but still missing content.
    kwargs["goto_options"] = {
        "wait_until": "networkidle",
        **kwargs.pop("goto_options", {}),
    }
    crawler = PlaywrightCrawler(
        browser_pool=BrowserPool(
            plugins=[CamoufoxPlugin(browser_launch_options=LAUNCH_OPTIONS)]
        ),
        **kwargs,
    )

    @crawler.post_navigation_hook
    async def _hook(context: PlaywrightPostNavCrawlingContext) -> None:
        # A DeniedError here fails the request; crawlee retries it (up to
        # max_request_retries, 3 by default) against a different browser
        # from the pool, same as fetch_html() retries below.
        await _pass_challenge(context.page)

    return crawler


async def fetch_html(url: str, **kwargs: Any) -> str:
    """Fetch a page's HTML via Camoufox, for one-off fetches outside crawlee.

    Retries with a fresh browser session (and so a fresh fingerprint) if
    CSFD denies the request outright rather than offering a challenge to
    solve, since that isn't recoverable within the same session.
    """
    kwargs.setdefault("wait_until", "networkidle")
    error: DeniedError | None = None
    for _ in range(FETCH_ATTEMPTS):
        async with AsyncCamoufox(headless=True, **LAUNCH_OPTIONS) as browser:
            page = await browser.new_page()
            await page.goto(url, **kwargs)
            try:
                await _pass_challenge(page)
                return await page.content()
            except DeniedError as exc:
                error = exc
    raise error
