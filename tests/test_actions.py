import json
import unittest
from unittest.mock import patch
from smartgpt.actions import FetchAction

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

if __name__ == "__main__":
    unittest.main()
