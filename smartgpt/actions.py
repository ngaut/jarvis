from dataclasses import dataclass, field
import io, subprocess, os, inspect, json, logging, time, re
import shutil
import venv
from typing import Union, List, Dict, Tuple
from abc import ABC
from urllib.error import HTTPError
import uuid
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse
import requests
import time
import hashlib
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager

from smartgpt import gpt
from smartgpt import jvm
from smartgpt.spinner import Spinner


_cache = {}

def load_cache():
    global _cache
    if os.path.exists("cache.json"):
        with open("cache.json", "r") as f:
            _cache = json.load(f)

def get_from_cache(key):
    global _cache
    return _cache.get(key, None)

def save_to_cache(key, value):
    global _cache
    _cache[key] = value
    with open("cache.json", "w") as f:
        json.dump(_cache, f)

@dataclass(frozen=True)
class Action(ABC):
    @classmethod
    def from_dict(cls, data: Union[str, dict]):
        if isinstance(data, str):
            data = json.loads(data)  # Parse the input string into a dictionary

        action_type = data.get("type")

        if action_type is None or action_type not in ACTION_CLASSES:
            return None

        action_class = ACTION_CLASSES[action_type]

        # Get the constructor parameters for the action class
        constructor_params = inspect.signature(action_class).parameters

        # Create a dictionary of constructor arguments from the JSON data
        constructor_args = {}
        for param_name, _ in constructor_params.items():
            if param_name != "self" and param_name in data:
                constructor_args[param_name] = data[param_name]

        return action_class(**constructor_args)

    def id(self) -> int:
        raise NotImplementedError

    def key(self) -> str:
        raise NotImplementedError

    def short_string(self) -> str:
        raise NotImplementedError

    def run(self) -> str:
        """Returns what jarvis should learn from running the action."""
        raise NotImplementedError

# add a new action class
@dataclass(frozen=True)
class FetchAction:
    action_id: int
    url: str
    save_to: str = None  # the key that will be used to save content to database

    def key(self):
        return "Fetch"

    def id(self) -> int:
        return self.action_id

    def short_string(self):
        return f"action_id: {self.id()}, Fetch `{self.url}`."

    @staticmethod
    def ensure_url_scheme(url) -> str:
        parsed = urlparse(url)
        if not parsed.scheme:
            parsed = parsed._replace(scheme='https', netloc=parsed.path, path='')
        return urlunparse(parsed)

    @staticmethod
    def get_html(url: str) -> str:
        # Setting up Chrome Options
        chrome_options = ChromeOptions()
        chrome_options.headless = True

        # Installing and setting up Chrome WebDriver with the defined options
        driver_path = ChromeDriverManager().install()

        # Use context management to ensure the browser is quit
        with ChromeWebDriver(executable_path=driver_path, options=chrome_options) as browser:
            # Access the provided URL
            browser.get(url)

            # Extract HTML content from the body of the web page
            body_element = browser.find_element(By.TAG_NAME, "body")
            page_html = body_element.get_attribute("innerHTML")

        return page_html

    @staticmethod
    def extract_text(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style"]):
            script.extract()

        # modify a tags to include href in markdown format
        for a in soup.find_all('a'):
            url = a.get('href', '')
            if url:
                a.string = f"[{a.get_text()}]({url})"

        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)
        return text

    def run(self):
        # Check if the url is already in the cache
        cached_key = self.url + self.save_to
        cached_result = get_from_cache(cached_key)
        if cached_result is not None:
            logging.info(f"\nFetchAction RESULT(cached)\n")
            return cached_result

        try:
            url = self.ensure_url_scheme(self.url)
            html = self.get_html(url)
            text = self.extract_text(html)
        except Exception as err:
            logging.error(f"FetchAction RESULT: An error occurred: {str(err)}")
            return f"FetchAction RESULT: An error occurred: {str(err)}"
        else:
            logging.info(f"\nFetchAction RESULT:\n{text}")
            result_json = {"kvs": [{"key": self.save_to, "value": text}]}
            result_json_str = json.dumps(result_json)

            save_to_cache(cached_key, result_json_str)
            return result_json_str

@dataclass(frozen=True)
class WebSearchAction:
    action_id: int
    query: str
    save_to: str # the key that will be used to save content to database

    def key(self):
        return "WebSearch"

    def id(self) -> int:
        return self.action_id

    def short_string(self):
        return f"action_id: {self.id()}, Search online for `{self.query}`."

    def run(self):
        # Check if the query is already in the cache
        cached_key = self.query + self.save_to
        cached_result = get_from_cache(cached_key)
        if cached_result is not None:
            logging.info(f"\nWebSearchAction RESULT(cached)\n")
            return cached_result

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'q': self.query,
            'num': 5,
            'key': os.getenv("GOOGLE_API_KEY"),
            'cx': os.getenv("GOOGLE_SEARCH_ENGINE_ID"),
        }

        for _ in range(3):  # retry for 3 times
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()  # raise exception if the request was unsuccessful

                search_results = response.json()
                if not search_results.get('items'):
                    logging.error(f"WebSearchAction RESULT: The online search for `{self.query}` appears to have failed.")
                    continue  # retry on failure

                # return a list of links
                result = [item['link'] for item in search_results['items']]
                logging.info(f"WebSearchAction RESULT: {result}")

                result_json = {"kvs": [{"key": self.save_to, "value": result}]}
                result_json_str = json.dumps(result_json)

                save_to_cache(cached_key, result_json_str)
                return result_json_str
            except requests.exceptions.HTTPError as http_err:
                if http_err.response.status_code == 429:
                    time.sleep(30)
                else:
                    logging.error(f"WebSearchAction RESULT: An HTTP error occurred: {http_err}")
            except Exception as err:
                logging.error(f"WebSearchAction RESULT: An error occurred: {err}")
        return "WebSearchAction RESULT: Max retry limit reached."

@dataclass(frozen=True)
class ExtractInfoAction(Action):
    action_id: int
    command: str
    content: str
    output_fmt: str
    model_name: str = gpt.GPT_3_5_TURBO

    def key(self) -> str:
        return "ExtractInfo"

    def id(self) -> int:
        return self.action_id

    def short_string(self) -> str:
        return f"action_id: {self.id()}, Extract info."

    def generate_messages(self) -> List[Dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that follows user's request. the format of key: 'key_<idx>.seqX.<type>', "
                    "where 'X' is a constant, value of <idx> is evaluated dynamically, 'type' is type of the value"
                    "(which can be one of Python's type {int, str, list}), list means list of strings, int means integer, "
                    "str means string. The user's request has three parts: Request, Output_fmt, Content. You will extract "
                    "information from the Content based on the Request and return the result in the format of Output_fmt."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Request={self.command}\n\nOutput_fmt={self.output_fmt}\n\nContent=```{self.content}```\n\nExtractInfoResult="
                )
            },
        ]

    def calculate_token_count(self, messages: List[Dict[str, str]]) -> Tuple[int, str]:
        request_token_count = gpt.count_tokens(messages)
        max_token_count = gpt.max_token_count(self.model_name)

        if request_token_count + 1024 > max_token_count:  # leave some space for the response
            max_token_count = gpt.max_token_count(gpt.GPT_3_5_TURBO_16K)
            return max_token_count - request_token_count, gpt.GPT_3_5_TURBO_16K

        return max_token_count - request_token_count, self.model_name

    def run(self) -> str:
        hash_str = hashlib.md5(self.command.encode()).hexdigest()
        cached_key = f"{hash_str}"
        cached_result = get_from_cache(cached_key)

        if cached_result is not None:
            logging.info(f"ExtractInfoAction RESULT(cached) for command \"{self.command}\"\n")
            return cached_result

        messages = self.generate_messages()
        max_response_token_count, model_name = self.calculate_token_count(messages)

        try:
            response = gpt.send_message(messages, max_response_token_count, model=model_name)
            if response is None:
                return f"ExtractInfoAction RESULT: Extract information for `{self.command}` appears to have failed."

            result = str(response)
            save_to_cache(cached_key, result)
            return result

        except Exception as err:
            return f"ExtractInfoAction RESULT: An error occurred: {str(err)}"

@dataclass(frozen=True)
class RunPythonAction(Action):
    action_id: int
    file_name: str = "tmp.py"
    timeout: int = 30 # in seconds
    code: str = ""
    pkg_dependencies: List[str] = field(default_factory=list)
    cmd_args: str = ""

    # Define the directory for the working environment
    work_dir = f'work_dir_{uuid.uuid4()}'

    def key(self) -> str:
        return "RunPython"

    def id(self) -> int:
        return self.action_id

    def short_string(self) -> str:
        return f"action_id: {self.id()}, Run Python file `{self.file_name} {self.cmd_args}`"

    def run(self) -> str:
        # Make sure filename and code aren't None
        if not self.file_name:
            return "RunPythonAction failed: The 'file_name' field argument can not be empty"
        if not self.code:
            return "RunPythonAction failed: The 'code' argument can not be empty"

        # Create work directory
        os.makedirs(self.work_dir, exist_ok=True)

         # Create virtual environment inside work directory
        venv_path = self._create_virtual_env()

        # Install dependencies in virtual environment
        self._install_dependencies(venv_path)

        # Write code to file inside work directory
        self._write_code_to_file()

        # Run the python script and fetch the output
        exit_code, stdout_output, stderr_error = self._run_script(venv_path)
        output = self._construct_output(exit_code, stdout_output, stderr_error)

        # Clean up working directory
        self._cleanup_work_dir()

        return output

    def _create_virtual_env(self):
        venv_dir = os.path.join(self.work_dir, 'venv')
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        return os.path.join(venv_dir, 'bin')

    def _install_dependencies(self, venv_path):
        for dependency in self.pkg_dependencies:
            subprocess.check_call([os.path.join(venv_path, 'pip'), 'install', dependency])

    def _write_code_to_file(self):
        with open(os.path.join(self.work_dir, self.file_name), mode="w", encoding="utf-8") as file:
            file.write(self.code)

    def _run_script(self, venv_path):
        with subprocess.Popen(
            [os.path.join(venv_path, 'python'), os.path.join(self.work_dir, self.file_name)] + self.cmd_args.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        ) as process:
            try:
                stdout_output, stderr_error = process.communicate(timeout=self.timeout)
                return process.returncode, stdout_output, stderr_error
            except subprocess.TimeoutExpired:
                process.kill()
                return 1, "", f"RunPythonAction failed: The Python script at `{self.file_name} {self.cmd_args}` timed out after {self.timeout} seconds."

    def _construct_output(self, exit_code, stdout_output, stderr_error):
        output = f"\n`python {self.file_name} {self.cmd_args}` returned: \n#exit code {exit_code}\n"
        if stdout_output:
            output += f"#stdout of process:\n{stdout_output}"
        if stderr_error:
            output += f"#stderr of process:\n{stderr_error}"
        if exit_code != 0:
            output += f"\n\nPython script code:\n{self.code}"
        return output

    def _cleanup_work_dir(self):
        shutil.rmtree(self.work_dir, ignore_errors=True)

@dataclass(frozen=True)
class TextCompletionAction(Action):
    action_id: int
    command: str
    content: str
    save_to: str
    model_name: str = gpt.GPT_3_5_TURBO

    def key(self) -> str:
        return "TextCompletion"

    def id(self) -> int:
        return self.action_id

    def short_string(self) -> str:
        return f"action_id: {self.id()}, Text Completion for `{self.command}`."

    def generate_messages(self) -> List[Dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant that completes the provided content according to the user's request."
                    "The user's input has two parts: Request, Content. You need to complete the Content according to the Request."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Request={self.command}\n\nContent=```{self.content}```\n\nTextCompletionResult:"
                )
            }
        ]

    def calculate_token_count(self, messages: List[Dict[str, str]]) -> Tuple[int, str]:
        request_token_count = gpt.count_tokens(messages)
        max_token_count = gpt.max_token_count(self.model_name)

        if request_token_count + 1024 > max_token_count:  # leave some space for the response
            max_token_count = gpt.max_token_count(gpt.GPT_3_5_TURBO_16K)
            return max_token_count - request_token_count, gpt.GPT_3_5_TURBO_16K

        return max_token_count - request_token_count, self.model_name


    def run(self) -> str:
        hash_str = hashlib.md5(self.command.encode()).hexdigest()
        cached_key = f"{hash_str}"
        cached_result = get_from_cache(cached_key)

        if cached_result is not None:
            logging.info(f"TextCompletionAction RESULT(cached) for command \"{self.command}\"\n")
            return cached_result

        messages = self.generate_messages()
        max_response_token_count, model_name = self.calculate_token_count(messages)

        try:
            response = gpt.send_message(messages, max_response_token_count, model=model_name)
            if response is None:
                return f"TextCompletionAction RESULT: generating text completion for `{self.command}` appears to have failed."

            result_json = {"kvs": [{"key": self.save_to, "value": response}]}
            result_json_str = json.dumps(result_json)

            save_to_cache(cached_key, result_json_str)
            return result_json_str

        except Exception as err:
            logging.error(f"TextCompletionAction RESULT: An error occurred: {str(err)}")
            return f"TextCompletionAction RESULT: An error occurred: {str(err)}"

# Helper function to populate the ACTION_CLASSES dictionary
def _populate_action_classes(action_classes):
    result = {}
    for action_class in action_classes:
        # Get the parameters of the __init__() method for this action class
        init_params = inspect.signature(action_class.__init__).parameters

        # Construct a dictionary of default argument values for the __init__() method
        default_args = {}
        for param in init_params.values():
            if param.name != "self":
                default_args[param.name] = param.default

        # Create an instance of the action class with the default arguments
        action_instance = action_class(**default_args)

        # Add the action class to the result dictionary, using the key returned by the key() method
        result[action_instance.key()] = action_class

    return result

ACTION_CLASSES = _populate_action_classes([
    FetchAction,
    RunPythonAction,
    ExtractInfoAction,
    WebSearchAction,
    TextCompletionAction,
])
