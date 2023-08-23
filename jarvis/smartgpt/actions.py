from dataclasses import dataclass, field
import subprocess
import os
import inspect
import json
import logging
import time
import venv
from typing import Union, List, Dict
from abc import ABC
import uuid
from urllib.parse import urlparse, urlunparse
import hashlib
from sys import platform
import requests

from bs4 import BeautifulSoup
import yaml

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver

from jarvis.smartgpt import gpt
from jarvis.smartgpt import jvm
from jarvis.smartgpt import utils
from jarvis.smartgpt import preprompts


TEXT_COMPLETION_MODEL = gpt.GPT_3_5_TURBO_16K

_CACHE = {}
_ENABLE_CACHE = True

def load_cache():
    global _CACHE
    if os.path.exists("cache.json"):
        with open("cache.json", "r") as f:
            _CACHE = json.load(f)
    else:
        _CACHE = {}

def enable_cache():
    global _ENABLE_CACHE
    _ENABLE_CACHE = True

def disable_cache():
    global _ENABLE_CACHE
    _ENABLE_CACHE = False

def get_from_cache(key):
    if _ENABLE_CACHE:
        return _CACHE.get(key, None)
    else:
        return None

def save_to_cache(key, value):
    if not _ENABLE_CACHE:
        return None

    _CACHE[key] = value
    with open("cache.json", "w") as f:
        json.dump(_CACHE, f)

@dataclass(frozen=True)
class Action(ABC):
    @classmethod
    def from_dict(cls, data: Union[str, dict]):
        if isinstance(data, str):
            data = yaml.safe_load(data)  # Parse the input string into a dictionary

        action_type = data.get("type")  # type: ignore

        if action_type is None or action_type not in ACTION_CLASSES:
            return None

        action_class = ACTION_CLASSES[action_type]

        # Get the constructor parameters for the action class
        constructor_params = inspect.signature(action_class).parameters

        # Create a dictionary of constructor arguments from the data
        constructor_args = {}
        for param_name, _ in constructor_params.items():
            if param_name != "self" and param_name in data:
                constructor_args[param_name] = data[param_name] # type: ignore

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

@dataclass(frozen=True)
class FetchWebContentAction:
    action_id: int
    url: str
    save_to: str = ""  # the key that will be used to save content to database

    def key(self):
        return "FetchWebContent"

    def id(self) -> int:
        return self.action_id

    def short_string(self):
        return f"action_id: {self.id()}, Fetch URL: `{self.url}`."

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

        chrome_options.add_argument('--no-sandbox')
        if platform == "linux" or platform == "linux2":
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--remote-debugging-port=9222")

        # Installing and setting up Chrome WebDriver with the defined options
        driver_path = ChromeDriverManager("116.0.5845.96").install()

        # Use context management to ensure the browser is quit
        with ChromeWebDriver(executable_path=driver_path, options=chrome_options) as browser:
        # with webdriver.Chrome(options=chrome_options) as browser:
            # Access the provided URL
            browser.get(url)

            # Extract HTML content from the body of the web page
            body_element = browser.find_element(By.TAG_NAME, "body")
            page_html = body_element.get_attribute("innerHTML")
            browser.quit()

        return page_html

    @staticmethod
    def extract_text(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style"]):
            script.extract()

        # modify a tags to include href in markdown format
        for a in soup.find_all('a'):
            url = a.get('href', '')

            # Only modify the link if it's an external link (i.e., starts with 'http' or 'https')
            if url and (url.startswith('http://') or url.startswith('https://')):
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
            logging.debug("FetchWebContentAction RESULT(cached).")
            return cached_result

        try:
            url = self.ensure_url_scheme(self.url)
            html = self.get_html(url)
            text = self.extract_text(html)
        except Exception as err:
            logging.error(f"FetchWebContentAction RESULT: An error occurred: {str(err)}")
            raise ValueError(f"FetchWebContentAction RESULT: An error occurred: {str(err)}")
            return f"FetchWebContentAction RESULT: An error occurred: {str(err)}"
        else:
            logging.debug(f"\nFetchWebContentAction RESULT:\n{text}")
            result_str = json.dumps({"kvs": [{"key": self.save_to, "value": text}]})

            save_to_cache(cached_key, result_str)
            return result_str

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
            'num': 3,
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
                logging.debug(f"WebSearchAction RESULT: {result}")

                result_str = json.dumps({"kvs": [{"key": self.save_to, "value": result}]})

                save_to_cache(cached_key, result_str)
                return result_str
            except requests.exceptions.HTTPError as http_err:
                if http_err.response.status_code == 429:
                    time.sleep(30)
                else:
                    logging.error(f"WebSearchAction RESULT: An HTTP error occurred: {http_err}")
            except Exception as err:
                logging.error(f"WebSearchAction RESULT: An error occurred: {err}")

        return "WebSearchAction RESULT: Max retry limit reached."


@dataclass(frozen=True)
class RunPythonAction(Action):
    action_id: int
    timeout: int = 30 # in seconds
    code: str = ""
    pkg_dependencies: List[str] = field(default_factory=list)
    cmd_args: str = ""

    # Keep the project's Python path
    project_dir = os.getcwd()

    def key(self) -> str:
        return "RunPython"

    def id(self) -> int:
        return self.action_id

    def short_string(self) -> str:
        return f"action_id: {self.id()}, Run Python code."

    def run(self) -> str:
        # Use the current directory as the working environment
        work_dir = os.getcwd()

        # Generate a random file name for each execution
        file_name = f'run_{uuid.uuid4()}.py'

        # Make sure code isn't None
        if not self.code:
            return "RunPythonAction failed: The 'code' argument can not be empty"

        # Create or use existing virtual environment
        venv_path = self._create_or_use_virtual_env(work_dir)

        # Install dependencies in virtual environment

        self._install_dependencies(venv_path)

        # Write code to file
        self._write_code_to_file(work_dir, file_name)

        # Run the python script and fetch the output
        exit_code, stdout_output, stderr_error = self._run_script(venv_path, work_dir, file_name)
        output = self._construct_output(exit_code, stdout_output, stderr_error, work_dir, file_name)

        return output

    def _create_or_use_virtual_env(self, work_dir):
        venv_dir = os.path.join(work_dir, 'venv')
        if not os.path.exists(venv_dir):
            venv.EnvBuilder(with_pip=True).create(venv_dir)
        return os.path.join(venv_dir, 'bin')

    def _install_dependencies(self, venv_path):
        for dependency in self.pkg_dependencies:
            subprocess.check_call([os.path.join(venv_path, 'pip'), 'install', dependency])

    def _write_code_to_file(self, work_dir, file_name):
        with open(os.path.join(work_dir, file_name), mode="w", encoding="utf-8") as file:
            file.write("import sys\n")
            file.write(f"sys.path.append('{self.project_dir}')\n")
            file.write("from jarvis.smartgpt import jvm\n")
            file.write("jvm.load_kv_store()\n")
            file.write(self.code)

    def _run_script(self, venv_path, work_dir, file_name):
        script_full_path = os.path.join(work_dir, file_name)
        with subprocess.Popen(
            [os.path.join(venv_path, 'python'), script_full_path] + self.cmd_args.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        ) as process:
            try:
                stdout_output, stderr_error = process.communicate(timeout=self.timeout)
                return process.returncode, stdout_output, stderr_error
            except subprocess.TimeoutExpired:
                process.kill()
                return 1, "", f"RunPythonAction failed: The Python script at `{script_full_path} {self.cmd_args}` timed out after {self.timeout} seconds."

    def _construct_output(self, exit_code, stdout_output, stderr_error, work_dir, file_name):
        script_full_path = os.path.join(work_dir, file_name)
        output = f"\n`python {script_full_path} {self.cmd_args}` returned: \n#exit code {exit_code}\n"
        if stdout_output:
            output += f"#stdout of process:\n{stdout_output}"
        if stderr_error:
            output += f"#stderr of process:\n{stderr_error}"
        if exit_code != 0:
            output += f"\n\nPython script code:\n{self.code}"
        return output

@dataclass(frozen=True)
class TextCompletionAction(Action):
    action_id: int
    request: str
    content: str
    output_format: str
    model_name: str = TEXT_COMPLETION_MODEL

    def key(self) -> str:
        return "TextCompletion"

    def id(self) -> int:
        return self.action_id

    def short_string(self) -> str:
        return f"action_id: {self.id()}, text completion for Request: \"{self.request}\"."

    def generate_messages(self) -> List[Dict[str, str]]:
        # Adjust content to fit within model's max tokens
        content = self.content
        max_token_count = gpt.get_max_tokens(gpt.GPT_3_5_TURBO_16K) - 4096  # leaving some space for the system and user roles and responses
        content_token_count = gpt.count_tokens(content)

        if content_token_count > max_token_count:
            # If content is too long, truncate it to fit within model's max tokens.
            content = gpt.truncate_to_tokens(content, max_token_count)

        user_prompt = preprompts.get("text_completion_user").format(
            request = self.request,
            output_format = utils.remove_quoted_token(self.output_format, "<to_fill>"),
            content = content,
        )

        messages = [
            {
                "role": "system",
                "content": preprompts.get("text_completion_sys"),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

        return messages

    def adjust_token_and_model(self, messages: List[Dict[str, str]]) -> str:
        request_token_count = gpt.count_tokens(messages)
        max_token_count = gpt.get_max_tokens(self.model_name)
        model_name = self.model_name

        if request_token_count + 1024 > max_token_count:  # leave some space for the response
            model_name = gpt.GPT_3_5_TURBO_16K

        return model_name

    def run(self) -> str:
        hash_key = self.request + str(jvm.get('idx'))
        hash_str = hashlib.md5(hash_key.encode()).hexdigest()
        cached_key = f"{hash_str}"
        cached_result = get_from_cache(cached_key)

        if cached_result is not None:
            logging.debug(f"TextCompletionAction RESULT(cached) for Request: {self.request}")
            return cached_result

        messages = self.generate_messages()
        model_name = self.adjust_token_and_model(messages)

        try:
            result = gpt.send_messages(messages, model_name)
            if result is None:
                raise ValueError("Generating text completion appears to have failed.")
            result = utils.strip_json(result)

            save_to_cache(cached_key, result)
            return result

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
    FetchWebContentAction,
    RunPythonAction,
    WebSearchAction,
    TextCompletionAction,
])
