import hashlib
import yaml
import unittest
from unittest.mock import patch
from smartgpt.actions import FetchAction
from smartgpt.actions import WebSearchAction
from smartgpt.actions import RunPythonAction
from smartgpt.actions import TextCompletionAction

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
        expected_result = yaml.safe_dump({
            "kvs": [
                {"key": self.action.save_to, "value": "Hello World!"}
            ]
        })
        self.assertEqual(self.action.run(), yaml.safe_load(expected_result, Loader=yaml.FullLoader))
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

class TestRunPythonAction(unittest.TestCase):
    def setUp(self):
        # Create a simple action
        self.action = RunPythonAction(
            action_id=1,
            code="print('Hello, World!')",
            timeout=5
        )

    def test_run(self):
        # Call run method of the action
        output = self.action.run()

        # Check if the output is as expected
        self.assertIn("#stdout of process:\nHello, World!\n", output)

    def test_run_with_timeout(self):
        # Create an action that runs an infinite loop
        self.action = RunPythonAction(
            action_id=1,
            code="while True: pass",
            timeout=1
        )
        # Call run method of the action
        output = self.action.run()

        # Check if the output indicates a timeout error
        self.assertIn("timed out after", output)

    def test_run_with_python_error(self):
        # Create an action that runs incorrect Python code
        self.action = RunPythonAction(
            action_id=1,
            code="print(1/0)",
            timeout=5
        )
        # Call run method of the action
        output = self.action.run()

        # Check if the output includes Python's ZeroDivisionError message
        self.assertIn("ZeroDivisionError", output)

    def test_run_with_dependency(self):
        # Create an action that needs the requests package
        self.action = RunPythonAction(
            action_id=1,
            code="import requests",
            pkg_dependencies=['requests'],
            timeout=5
        )
        # Call run method of the action
        output = self.action.run()

        # Check if the output does not indicate an ImportError
        self.assertNotIn("ImportError", output)

    def test_run_with_dependency_and_usage(self):
        # Create an action that needs the numpy package
        # and uses it in the code to create an array and print it
        self.action = RunPythonAction(
            action_id=1,
            code="import numpy as np\narr = np.array([1, 2, 3, 4, 5])\nprint(arr)",
            pkg_dependencies=['numpy'],
            timeout=10
        )
        # Call run method of the action
        output = self.action.run()

        # Check if the output includes the printed numpy array
        self.assertIn("[1 2 3 4 5]", output)

class TestTextCompletion(unittest.TestCase):
    def setUp(self):
        self.action = TextCompletionAction(1, "Complete this text", "This is a test", '{"kvs": [{"weather_report.seq3.str":"<fill_later>"}]}')

    @patch('smartgpt.gpt.send_message')
    @patch('smartgpt.actions.save_to_cache')
    @patch('smartgpt.actions.get_from_cache')
    def test_run_send_message_error(self, mock_get_from_cache, mock_save_to_cache, mock_send_message):
        # Test case where the gpt.send_message method returns None, indicating an error
        mock_get_from_cache.return_value = None
        mock_send_message.return_value = None
        result = self.action.run()
        self.assertIn("appears to have failed.", result)
        mock_get_from_cache.assert_called_once()
        mock_save_to_cache.assert_not_called()
        mock_send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
