from pathlib import Path

import pytest

from kino.csfd import ChallengeError, get_csfd_crawler, raise_if_challenge


FIXTURES = Path(__file__).parent / "fixtures"


def test_raise_if_challenge_raises_on_challenge_page():
    body = (FIXTURES / "csfd_challenge.html").read_bytes()

    with pytest.raises(ChallengeError):
        raise_if_challenge("https://www.csfd.cz/film/1/", body)


@pytest.mark.parametrize("fixture", ["csfd_program.html", "csfd_vlastni_vyber.html"])
def test_raise_if_challenge_passes_real_pages(fixture):
    body = (FIXTURES / fixture).read_bytes()

    raise_if_challenge("https://www.csfd.cz/", body)


def test_csfd_crawler_sends_telegram_user_agent():
    # CSFD's anti-bot layer lets Telegram's link-preview crawler through.
    crawler = get_csfd_crawler()

    headers = crawler._http_client._async_client_kwargs["headers"]
    assert headers["User-Agent"] == "TelegramBot (like TwitterBot)"
