
from dataclasses import dataclass, field

import io, subprocess, os, inspect, json, logging, time, re
import gpt, jarvisvm
from spinner import Spinner
from typing import Union,List, Dict
from abc import ABC
from urllib.error import HTTPError
from bs4 import BeautifulSoup
import requests
import time
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



@dataclass(frozen=True)
class SearchOnlineAction:
    action_id: int
    query: str
    
    def key(self):
        return "SearchOnline"

    def id(self) -> int:
        return self.action_id
    
    def short_string(self):
        return f"action_id: {self.id()}, Search online for `{self.query}`."



    def run(self):
        try:
            # Check if the query is already in the cache
            cached_result = get_from_cache(self.query)
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
            jarvisvm.set(f"search_results.seqnum{self.action_id}", result)
            
            save_to_cache(self.query, str(result))

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
    url: str
    command: str


    def key(self) -> str:
        return "ExtractInfo"

    def id(self) -> int:
        return self.action_id
    
    def short_string(self) -> str:
        return f"action_id: {self.id()}, Extract info from `{self.url}`, with command:<{self.command}>."

    def run(self) -> str:
        key = f"{self.url}::{self.command}"
        cached_result = get_from_cache(key)
        if cached_result is not None:
            logging.info(f"\nExtractInfoAction RESULT(cached)\n")
            return cached_result
        
        with Spinner("Reading website..."):
            html = self.get_html(self.url)
        text = self.extract_text(html)
        user_message_content = f"{self.command}\n\nThe content of the web page:```{text}```"
    
        with Spinner("Extracting info..."):
            extracted_info = gpt.complete(user_message_content, model=gpt.GPT_3_5_TURBO)
        save_to_cache(key, extracted_info)
        return extracted_info

    def get_html(self, url: str) -> str:
        options = ChromeOptions()
        options.headless = True
        browser = ChromeWebDriver(executable_path=ChromeDriverManager().install(), options=options)
        browser.get(url)
        html = browser.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
        browser.quit()
        return html

    def extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)
        return text

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
                if dependency != "jarvisvm":
                    logging.info("Installing %s...", dependency)
                    os.system(f"pip install {dependency}")


    def _write_code_to_file(self):
        with io.open(self.file_name, mode="w", encoding="utf-8") as file:
            file.write("import jarvisvm\n")
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
        key = f"TextCompletionAction:{self.prompt}"
        cached_result = get_from_cache(key)
        if cached_result is not None:
            logging.info("\nTextCompletionAction RESULT(cached)\n")
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that uses AI to complete text.",
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
    RunPythonAction,
    ExtractInfoAction,
    SearchOnlineAction,
    TextCompletionAction,
])