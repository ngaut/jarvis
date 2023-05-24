
from dataclasses import dataclass, field

import io, subprocess, os, inspect, json, logging, time, re
import gpt
from spinner import Spinner
from typing import Union,List, Dict
from abc import ABC
from urllib.error import HTTPError
from bs4 import BeautifulSoup
import googlesearch
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
import sqlite3


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



    def key(self) -> str:
        raise NotImplementedError

    def short_string(self) -> str:
        raise NotImplementedError

    def run(self) -> str:
        """Returns what jarvis should learn from running the action."""
        raise NotImplementedError



@dataclass(frozen=True)
class SearchOnlineAction:
    query: str
    
    def key(self):
        return "SearchOnline"

    def short_string(self):
        return f"Search online for `{self.query}`."

    def run(self):
        try:
            response = list(googlesearch.search(self.query, num=15, stop=15, pause=2))
            if response is None:
                return f"SearchOnlineAction RESULT: The online search for `{self.query}` appears to have failed."

            result = "\n".join([str(url) for url in response])
            return result
        except HTTPError as http_err:
            if http_err.code == 429:
                time.sleep(30)
                return "SearchOnlineAction RESULT: Too many requests. Please try again later."
            else:
                return f"SearchOnlineAction RESULT: An HTTP error occurred: {http_err}"


@dataclass(frozen=True)
class ExtractInfoAction(Action):
    url: str
    instructions: str

    def key(self) -> str:
        return "ExtractInfo"

    def short_string(self) -> str:
        return f"Extract info from `{self.url}`: {self.instructions}."

    def run(self) -> str:
        with Spinner("Reading website..."):
            html = self.get_html(self.url)
        text = self.extract_text(html)
        logging.info("RESULT: The webpage at %s was read successfully.", self.url)
        user_message_content = f"{self.instructions}\n\n```\n{text[:3000]}\n```"
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant. You will be given instructions to extract some information from the contents of a website. Do your best to follow the instructions and extract the info.",
            },
            {"role": "user", "content": user_message_content},
        ]
        request_token_count = gpt.count_tokens(messages)
        max_response_token_count = gpt.max_token_count(gpt.GPT_3_5_TURBO) - request_token_count
        with Spinner("Extracting info..."):
            extracted_info = gpt.send_message(messages, max_response_token_count, model=gpt.GPT_3_5_TURBO)
        result = f"{self.short_string()}, The info extracted:{extracted_info}"
        logging.info(result)
        return result

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

# todo implement database related actions

@dataclass(frozen=True)
class RunPythonAction(Action):
    file_name: str
    timeout: int  = 30 # in seconds
    code:str = ""
    code_dependencies: list = field(default_factory=list)
    cmd_args: str = ""

    def key(self) -> str:
        return "RunPython"

    def short_string(self) -> str:
        return f"Run Python file `{self.file_name} {self.cmd_args}`."

    def run(self) -> str:
        if self.file_name is None:
            return f"RunPythonAction failed: The 'file_name' field argument can not be empty"
        if self.code is None or self.code == "":
            return "RunPythonAction failed: The 'code' argument can not be empty"
 
        # install dependencies
        for dependency in self.code_dependencies:
            with Spinner(f"Installing {dependency}..."):
                logging.info("Installing %s...", dependency)
                os.system(f"pip install {dependency}")
        code = self.code
        # write code to path and run
        with io.open(self.file_name, mode="w", encoding="utf-8") as file:
            file.write(code)
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
                include_source = False
                stderr_error = process.stderr.read() if process.stderr else ""
                # Use regex to find if there are any possible errors in the output of script
                if re.search(r"(?i)error|exception|fail|fatal", stdout_output + stderr_error):
                    include_source = True

                output = f"\n`python {self.file_name} {self.cmd_args}` returned: \n#exit code {exit_code}\n"
                if len(stdout_output) > 0:
                    output += f"#stdout of process:\n{stdout_output}"
                if len(stderr_error) > 0:
                    output += f"#stderr of process:\n{stderr_error}"
                if exit_code != 0 or include_source:
                    output += f"\n\nPython script code:\n{code}"
                return output
            except subprocess.TimeoutExpired:
                process.kill()
                output = f"RunPythonAction failed: The Python script at `{self.file_name} {self.cmd_args}` timed out after {self.timeout} seconds."
                return output


@dataclass(frozen=True)
class ShutdownAction(Action):
    summary: str

    def key(self):
        return "Shutdown"

    def short_string(self) -> str:
        return f"Shutdown:{self.summary}"

    def run(self) -> str:
        # This action is treated specially, so this can remain unimplemented.
        raise NotImplementedError
 

@dataclass(frozen=True)
class DbUpsertAction(Action):
    kvs: List[Dict[str, Union[str, dict]]]

    def key(self) -> str:
        return "DbUpsert"

    def short_string(self) -> str:
        return f"Upsert keys and values into the database."

    def run(self) -> str:
        conn = sqlite3.connect('my_database.db')
        c = conn.cursor()

        # Ensure the table is created
        c.execute('''CREATE TABLE IF NOT EXISTS kvstore
                    (key text primary key, value text)''')

        for kv in self.kvs:
            c.execute("INSERT OR REPLACE INTO kvstore VALUES (?, ?)", (kv['k'], json.dumps(kv['v'])))
        
        conn.commit()
        conn.close()
        return f"DbUpsertAction: Successfully upserted {len(self.kvs)} key-value pair(s) into the database."


@dataclass(frozen=True)
class DbQueryAction(Action):
    k: str

    def key(self) -> str:
        return "DbQuery"

    def short_string(self) -> str:
        return f"Query the value of `{self.k}` from the database."

    def run(self) -> str:
        conn = sqlite3.connect('my_database.db')
        c = conn.cursor()

        c.execute("SELECT value FROM kvstore WHERE key=?", (self.k,))

        row = c.fetchone()
        if row is None:
            return f"DbQueryAction: Key `{self.k}` does not exist in the database."

        value = json.loads(row[0])
        conn.close()
        return f"DbQueryAction: The value of key `{self.k}` in the database is {value}."


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
    ShutdownAction,
    ExtractInfoAction,
    SearchOnlineAction,
    DbUpsertAction,
    DbQueryAction,
])