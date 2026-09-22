from playwright.async_api import Page


CHALLENGE_TITLE = "Making sure you're not a bot!"


async def wait_out_challenge(page: Page, timeout: float = 60000) -> None:
    """Wait out CSFD's JS proof-of-work challenge page, if one was shown.

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
