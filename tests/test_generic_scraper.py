from winxtract.scrapers.generic_css import GenericCssScraper


def test_selector_engine_prefixes():
    scraper = GenericCssScraper()
    assert scraper._sel("css:.item") == ".item"
    assert scraper._sel("xpath://div[@id='x']") == "xpath=//div[@id='x']"
    assert scraper._sel("//article") == "xpath=//article"
    assert scraper._sel(".card") == ".card"
