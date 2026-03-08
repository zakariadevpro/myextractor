from winxtract.scrapers.pages_blanches import _build_seed_urls


def test_build_seed_urls_from_inline_params():
    urls = _build_seed_urls(
        {
            "seed_names": ["Martin", "Dupont"],
            "cities": ["Paris", "Lyon"],
            "max_queries": 3,
        }
    )
    assert len(urls) == 3
    assert urls[0].startswith("https://www.pagesjaunes.fr/pagesblanches/recherche?")
    assert "quoiqui=Martin" in urls[0]
    assert "ou=Paris" in urls[0]


def test_build_seed_urls_from_files(tmp_path):
    names = tmp_path / "names.txt"
    cities = tmp_path / "cities.txt"
    names.write_text("Martin\nDurand\n", encoding="utf-8")
    cities.write_text("Saint-Denis\n", encoding="utf-8")

    urls = _build_seed_urls(
        {
            "seed_names_file": str(names),
            "cities_file": str(cities),
            "max_queries": 10,
        }
    )
    assert len(urls) == 2
    # Ensure URL encoding is applied on city values.
    assert all("ou=Saint-Denis" in url for url in urls)
