import unittest

from crawler.sites.generic import build_generic_adapter


class GenericSiteAdapterTests(unittest.TestCase):
    def test_build_start_urls_encodes_keyword(self) -> None:
        adapter = build_generic_adapter("https://example.com/search?q={keyword}")
        self.assertEqual(
            adapter.build_start_urls("hello world"),
            ["https://example.com/search?q=hello+world"],
        )

    def test_parse_page_extracts_keyword_matches(self) -> None:
        adapter = build_generic_adapter("https://example.com/search?q={keyword}")
        parsed = adapter.parse_page(
            "https://example.com/search?q=apple",
            """
            <html>
              <head>
                <title>Apple Search</title>
                <meta name="description" content="search results">
              </head>
              <body>
                <a href="/item/1">Apple item</a>
                <p>apple pie and Apple juice</p>
              </body>
            </html>
            """,
            "apple",
        )

        self.assertEqual(parsed.title, "Apple Search")
        self.assertEqual(parsed.meta_description, "search results")
        self.assertEqual(parsed.links, ["https://example.com/item/1"])
        self.assertEqual(parsed.matches[0]["count"], 3)


if __name__ == "__main__":
    unittest.main()
