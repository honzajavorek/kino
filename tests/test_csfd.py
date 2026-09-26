from kino.csfd import get_csfd_crawler


def test_csfd_crawler_waits_for_domcontentloaded_not_load():
    # "load" waits for every subresource (ads, trackers) and can hang well
    # past the point a CSFD page's real content has already arrived - see
    # csfd.py's _pass_challenge docstring for the same reasoning applied to
    # the post-challenge reload.
    crawler = get_csfd_crawler()

    assert crawler._goto_options.get("wait_until") == "domcontentloaded"
