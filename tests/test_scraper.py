import unittest
from src.scraper.wiki_scraper import WikiScraper
from src.scraper.html_parser import HTMLParser

class TestWikiScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = WikiScraper()
        self.parser = HTMLParser()

    def test_scrape_content_risks(self):
        data = self.scraper.scrape_content_risks()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_parse_html(self):
        html_content = "<html><body><p>Test content related to privacy.</p></body></html>"
        parsed_data = self.parser.parse(html_content)
        self.assertIn("privacy", parsed_data)

if __name__ == '__main__':
    unittest.main()