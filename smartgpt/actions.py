
from dataclasses import dataclass, field

import io, subprocess, os, inspect, json, logging, time, re
import gpt, jvm
from spinner import Spinner
from typing import Union,List, Dict
from abc import ABC
from urllib.error import HTTPError
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import requests
import time
import hashlib
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager


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
    
    def get_html(self, url: str) -> str:
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
    
    def extract_text(self, html: str) -> str:
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
        try:
            # Check if the url is already in the cache
            cached_result = get_from_cache(f"{self.url}{self.save_to}")
            if cached_result is not None:
                logging.info(f"\nFetchAction RESULT(cached)\n")
                return cached_result
            
            url = self.url
            # todo: check if the url is valid, if missing http:// or https://, add it
            parsed = urlparse(url)
            if not bool(parsed.netloc) and bool(parsed.path):
                url = 'https://' + url
            elif not parsed.scheme:
                url = 'https://' + url

            html = self.get_html(url)
            text = self.extract_text(html)
            logging.info(f"\nFetchAction RESULT:\n{text}")

            jvm.set(self.save_to, text)
            save_to_cache(f"{self.url}{self.save_to}", text)
            return "success"
        except Exception as err:
            return f"FetchAction RESULT: An error occurred: {err}"

@dataclass(frozen=True)
class SearchOnlineAction:
    action_id: int
    query: str
    result_key: str  # the key that will be used to save content to database
    
    def key(self):
        return "SearchOnline"

    def id(self) -> int:
        return self.action_id
    
    def short_string(self):
        return f"action_id: {self.id()}, Search online for `{self.query}`."

    def run(self):
        try:
            # Check if the query is already in the cache
            cached_key = self.query + self.result_key
            cached_result = get_from_cache(cached_key)
            if cached_result is not None:
                logging.info(f"\nSearchOnlineAction RESULT(cached)\n")
                return cached_result
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'q': self.query,
                'num': 5,
                'key': "AIzaSyBXp89Jf292xF8eIBQqkCanZiOH58APRww",  
                'cx': 'f728c501aa4eb451c',
            }

            response = requests.get(url, params=params)
            response.raise_for_status()  # raise exception if the request was unsuccessful

            search_results = response.json()

            if not search_results.get('items'):
                return f"SearchOnlineAction RESULT: The online search for `{self.query}` appears to have failed."
            
            # return a list of links
            result = [item['link'] for item in search_results['items']]
            logging.info(f"SearchOnlineAction RESULT: {result}")
            jvm.set(self.result_key, result)
            
            save_to_cache(cached_key, str(result))

            return str(result)
        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 429:
                time.sleep(30)
                return "SearchOnlineAction RESULT: Too many requests. Please try again later."
            else:
                return f"SearchOnlineAction RESULT: An HTTP error occurred: {http_err}"
        except Exception as err:
            return f"SearchOnlineAction RESULT: An error occurred: {err}"



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

    def run(self) -> str:
        hash_str = hashlib.md5(self.command.encode()).hexdigest()
        key = f"{hash_str}"
        cached_result = get_from_cache(key)
        if cached_result is not None:
            logging.info(f"\nExtractInfoAction RESULT(cached)\n")
            return cached_result
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that follow user's request. the format of key: 'key_<idx>.seqX.<type>', where 'X' is a constant, value of <idx> is eval dynamically, 'type' is type of the value(which can be one of Python's type {int, str, list}), list means list of strings, int means integer, str means string."
                    f"The user's request has three parts: request, output_fmt, content. You will extract information from the content based on the request and return the result in the format of output_fmt."
                )
            },
            {
                "role": "user",
                "content": (
                    f"request={self.command}\n\noutput_fmt={self.output_fmt}\n\nContent={self.content}"
                )
            },
        ]

        model_name = self.model_name
        request_token_count = gpt.count_tokens(messages)
        if request_token_count + 1024 > gpt.max_token_count(self.model_name): # leave some space for the response
            max_response_token_count = gpt.max_token_count(gpt.GPT_3_5_TURBO_16K) - request_token_count
            model_name = gpt.GPT_3_5_TURBO_16K
        else:
            max_response_token_count = gpt.max_token_count(self.model_name) - request_token_count

        try:
            response = gpt.send_message(messages, max_response_token_count, model=model_name)
            if response is None:
                return f"TextCompletionAction RESULT: The text completion for `{self.command}` appears to have failed."

            result = str(response)
            save_to_cache(key, result)
            return result

        except Exception as e:
            return f"ExtractInfoAction RESULT: An error occurred: {e}"

    

@dataclass(frozen=True)
class RunPythonAction(Action):
    action_id: int
    file_name: str = "tmp.py"
    timeout: int  = 30 # in seconds
    code:str = ""
    pkg_dependencies: list = field(default_factory=list)
    cmd_args: str = ""    

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
        
        # Install code dependencies
        self._install_dependencies()

        # Write code to file
        self._write_code_to_file()

        # Run the python script and fetch the output
        output = self._run_script_and_fetch_output()
        return output

    def _install_dependencies(self):
        for dependency in self.pkg_dependencies:
            with Spinner(f"Installing {dependency}..."):
                if dependency != "jvm":
                    logging.info("Installing %s...", dependency)
                    os.system(f"pip install {dependency}")


    def _write_code_to_file(self):
        with io.open(self.file_name, mode="w", encoding="utf-8") as file:
            file.write("import jvm\n")
            file.write(self.code)


    def _run_script_and_fetch_output(self):
        with subprocess.Popen(
                f"python {self.file_name} {self.cmd_args}",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
        ) as process:
            try:
                exit_code = process.wait(timeout=self.timeout)  # Add the timeout argument
                stdout_output = process.stdout.read() if process.stdout else ""
                stderr_error = process.stderr.read() if process.stderr else ""

                include_source = False
                # Use regex to find if there are any possible errors in the output of script
                if re.search(r"(?i)error|exception|fail|fatal", stdout_output + stderr_error):
                    include_source = True

                output = self._construct_output(exit_code, stdout_output, stderr_error, include_source)
                return output

            except subprocess.TimeoutExpired:
                process.kill()
                output = f"RunPythonAction failed: The Python script at `{self.file_name} {self.cmd_args}` timed out after {self.timeout} seconds."
                return output


    def _construct_output(self, exit_code, stdout_output, stderr_error, include_source):
        output = f"\n`python {self.file_name} {self.cmd_args}` returned: \n#exit code {exit_code}\n"
        if stdout_output:
            output += f"#stdout of process:\n{stdout_output}"
        if stderr_error:
            output += f"#stderr of process:\n{stderr_error}"
        if exit_code != 0 or include_source:
            output += f"\n\nPython script code:\n{self.code}"

        return output


@dataclass(frozen=True)
class TextCompletionAction(Action):
    action_id: int
    prompt: str
    model_name: str = gpt.GPT_3_5_TURBO

    def key(self) -> str:
        return "TextCompletion"

    def id(self) -> int:
        return self.action_id

    def short_string(self) -> str:
        return f"action_id: {self.id()}, Text completion for `{self.prompt}`."

    def run(self) -> str:
        # use cache if possible
        hash_str = hashlib.md5(self.prompt.encode()).hexdigest()
        key = f"{hash_str}"
        cached_result = get_from_cache(key)
        if cached_result is not None:
            logging.info("\nTextCompletionAction RESULT(cached)\n")
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that uses AI to complete text.When constructing your response, please pay attention to <idx> and the postfix of key, idx starts from 0. the postfix of key indicates the type of value, such as: list, str,int and so on",
            },
            {"role": "user", "content": self.prompt},
        ]

        request_token_count = gpt.count_tokens(messages)
        max_response_token_count = gpt.max_token_count(self.model_name) - request_token_count

        try:
            response = gpt.send_message(messages, max_response_token_count, model=self.model_name)
            if response is None:
                return f"TextCompletionAction RESULT: The text completion for `{self.prompt}` appears to have failed."

            result = str(response)
            save_to_cache(key, result)
            return result

        except Exception as e:
            return f"TextCompletionAction RESULT: An error occurred: {e}"

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
    SearchOnlineAction,
    TextCompletionAction,
])