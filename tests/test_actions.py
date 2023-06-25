import json
import unittest
from unittest.mock import patch
from smartgpt.actions import FetchAction
from smartgpt.actions import WebSearchAction

class TestFetchAction(unittest.TestCase):
    def setUp(self):
        self.action = FetchAction(1, "https://news.ycombinator.com/", "content_fetched_0.seq3.str")

    def test_ensure_url_scheme(self):
        # Test case where url does not have a scheme
        self.assertEqual(
             FetchAction.ensure_url_scheme("www.google.com"),
             "https://www.google.com"
        )

        # Test case where url has http scheme
        self.assertEqual(
            FetchAction.ensure_url_scheme("http://www.google.com"),
            "http://www.google.com"
        )

        # Test case where url has https scheme
        self.assertEqual(
            FetchAction.ensure_url_scheme("https://www.google.com"),
            "https://www.google.com"
        )

    def test_extract_text(self):
        html = """
        <html>
        <body>
        <script>console.log('Hello, World!');</script>
        <p>Hello, World!</p>
        </body>
        </html>
        """
        text = FetchAction.extract_text(html)
        self.assertNotIn("console.log('Hello, World!');", text)
        self.assertIn("Hello, World!", text)

    @patch.object(FetchAction, 'get_html', return_value='<html><body><p>Hello World!</p></body></html>')
    def test_run(self, mock_get_html):
        expected_result = json.dumps({
            "kvs": [
                {"key": self.action.save_to, "value": "Hello World!"}
            ]
        })
        self.assertEqual(self.action.run(), expected_result)
        mock_get_html.assert_called_once()

class TestWebSearchAction(unittest.TestCase):
    def setUp(self):
        self.action = WebSearchAction(1, "hacker news", "search_url.seq3.list")

    def test_id(self):
        self.assertEqual(self.action.id(), 1)

    def test_key(self):
        self.assertEqual(self.action.key(), "WebSearch")

    def test_short_string(self):
        self.assertEqual(self.action.short_string(), "action_id: 1, Search online for `hacker news`.")

    @patch('smartgpt.actions.requests.get')
    @patch('smartgpt.actions.save_to_cache')
    @patch('smartgpt.actions.get_from_cache')
    def test_run(self, mock_cache_get, mock_cache_save, mock_requests_get):
        # assume that there is no cache for the query
        mock_cache_get.return_value = None
        # assume that the http request was successful
        mock_requests_get.return_value.status_code = 200
        # assume that the request returns a json response
        mock_requests_get.return_value.json.return_value = {"items": [{"link": "https://news.ycombinator.com/"}]}

        result = self.action.run()
        expected_result = json.dumps({"kvs": [{"key": "search_url.seq3.list", "value": ["https://news.ycombinator.com/"]}]})

        self.assertEqual(result, expected_result)
        mock_cache_save.assert_called_once()

if __name__ == "__main__":
    unittest.main()
