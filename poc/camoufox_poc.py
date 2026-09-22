"""Throwaway PoC: does Camoufox get past csfd.cz's anti-bot wall?

Not part of the kino package, not wired into pyproject.toml. Delete this file
and .github/workflows/camoufox-poc.yml once we know the answer.
"""

import asyncio
import sys

from camoufox.async_api import AsyncCamoufox


URLS = [
    "https://www.csfd.cz/zebricky/vlastni-vyber/",  # kino's flags.py target
    "https://www.csfd.cz/film/1308202-jeden-den/prehled/",  # film2trello's failing URL
]

CHALLENGE_TITLE = "Making sure you're not a bot!"


async def check(url: str) -> bool:
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        response = await page.goto(url, wait_until="load", timeout=30000)
        if await page.title() == CHALLENGE_TITLE:
            # The challenge page runs a PoW hash loop client-side (visible as
            # "Calculating... Speed: NkH/s"); "load" fires long before that
            # finishes, so wait for the title to move on instead of snapshotting
            # the page mid-computation.
            try:
                await page.wait_for_function(
                    "(expected) => document.title !== expected",
                    arg=CHALLENGE_TITLE,
                    timeout=60000,
                )
            except Exception as exc:
                print(f"still on challenge page after 60s: {exc}")
        title = await page.title()
        body = (await page.inner_text("body"))[:500]

    print(f"\n=== {url} ===")
    print(f"status: {response.status if response else None}")
    print(f"title: {title!r}")
    print(f"body preview: {body!r}")

    blocked = title == CHALLENGE_TITLE or "denied" in title.lower()
    print(f"blocked: {blocked}")
    return not blocked


async def main() -> int:
    results = [await check(url) for url in URLS]
    passed = sum(results)
    print(f"\n{'PASS' if passed == len(results) else 'FAIL'}: {passed}/{len(results)} URLs got through")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
