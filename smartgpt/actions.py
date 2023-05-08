
from dataclasses import dataclass
import os
import io
import stat
import subprocess
from spinner import Spinner
import gpt
import inspect
import json
from typing import Union, Optional
from abc import ABC
from bs4 import BeautifulSoup
from googlesearch import search
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager


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
class TellUserAction(Action):
    text: str

    def key(self) -> str:
        return "TELL_USER"

    def short_string(self) -> str:
        return f'Tell user "{self.text}".'

    def run(self) -> str:
        return f"Told user the following: {self.text}"


@dataclass(frozen=True)
class ReadFileAction(Action):
    path: str

    def key(self) -> str:
        return "READ_FILE"

    def short_string(self) -> str:
        return f"Read file `{self.path}`."

    def run(self) -> str:
        # Check if the path is a local file
        if os.path.exists(self.path):
            with io.open(self.path, mode="r", encoding="utf-8") as file:
                contents = file.read()
                return contents
        else:
                return f"Failed to read file, File `{self.path} not exist`"


@dataclass(frozen=True)
class WriteFileAction(Action):
    path: str
    text: Optional[str] = None

    def key(self) -> str:
        return "WRITE_FILE"

    def short_string(self) -> str:
        return f"Write file `{self.path}`."

    def run(self) -> str:
        with io.open(self.path, mode="w", encoding="utf-8") as file:
            bytes_written = file.write(self.text)
            print(f"WriteFileAction RESULT: Wrote file `{self.path}`.")
            return f"WriteFileAction: File successfully written with {bytes_written} bytes."


@dataclass(frozen=True)
class AppendFileAction(Action):
    path: str
    text: str

    def key(self) -> str:
        return "APPEND_FILE"

    def short_string(self) -> str:
        return f"Append file `{self.path}`."

    def run(self) -> str:
        with io.open(self.path, mode="a", encoding="utf-8") as file:
            bytes_written = file.write(self.text)
            print(f"AppendFileAction RESULT: Appended file `{self.path}`.")
            return f"AppendFileAction File successfully appended with {bytes_written} bytes"

@dataclass(frozen=True)
class CreateDirectoryAction(Action):
    path: str

    def key(self) -> str:
        return "CREATE_DIRECTORY"

    def short_string(self) -> str:
        return f"Create directory `{self.path}`."

    def run(self) -> str:
        try:
            os.makedirs(self.path)
            print(f"CreateDirectoryAction RESULT: Created directory `{self.path}`.")
            return "CreateDirectoryAction: Directory successfully created."
        except FileExistsError:
            print(f"CreateDirectoryAction RESULT: Directory `{self.path}` already exists.")
            return f"CreateDirectoryAction: Directory '{self.path}' already exists."


@dataclass(frozen=True)
class RunPythonAction(Action):
    path: str
    timeout: int  # Add the timeout parameter (in seconds)

    def key(self) -> str:
        return "RUN_PYTHON"

    def short_string(self) -> str:
        return f"Run Python file `{self.path}`."

    def run(self) -> str:
        with subprocess.Popen(
            f"python {self.path}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        ) as process:
            try:
                process.wait(timeout=self.timeout)  # Add the timeout argument
                output = process.stdout.read() if process.stdout else ""
                print(f"RunPythonAction RESULT: Ran Python file `{self.path}`.")
                return output
            except subprocess.TimeoutExpired:
                process.kill()
                return f"RunPythonAction failed: The Python script at `{self.path}` timed out after {self.timeout} seconds."


@dataclass(frozen=True)
class SearchOnlineAction(Action):
    query: str

    def key(self) -> str:
        return "SEARCH_ONLINE"

    def short_string(self) -> str:
        return f"Search online for `{self.query}`."

    def run(self) -> str:
        response = search(self.query, num=10)
        if response is None:
            return f"SearchOnlineAction RESULT: The online search for `{self.query}` appears to have failed."
        result = "\n".join([str(url) for url in response])
        print(f"SearchOnlineAction RESULT: The online search for `{self.query}` returned the following URLs:\n{result}")
        return result


@dataclass(frozen=True)
class ExtractInfoAction(Action):
    url: str
    instructions: str

    def key(self) -> str:
        return "EXTRACT_INFO"

    def short_string(self) -> str:
        return f"Extract info from `{self.url}`: {self.instructions}."

    def run(self) -> str:
        with Spinner("Reading website..."):
            html = self.get_html(self.url)
        text = self.extract_text(html)
        print(f"RESULT: The webpage at `{self.url}` was read successfully.")
        user_message_content = f"{self.instructions}\n\n```\n{text[:10000]}\n```"
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant. You will be given instructions to extract some information from the contents of a website. Do your best to follow the instructions and extract the info.",
            },
            {"role": "user", "content": user_message_content},
        ]
        request_token_count = gpt.count_tokens(messages)
        max_response_token_count = gpt.COMBINED_TOKEN_LIMIT - request_token_count
        with Spinner("Extracting info..."):
            extracted_info = gpt.send_message(messages, max_response_token_count, model=gpt.GPT_3_5_TURBO)
        print("ExtractInfoAction RESULT: The info was extracted successfully.")
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
class ShutdownAction(Action):
    thoughts: str

    def key(self):
        return "SHUTDOWN"

    def short_string(self) -> str:
        return f"Shutdown:{self.thoughts}"

    def run(self) -> str:
        # This action is treated specially, so this can remain unimplemented.
        raise NotImplementedError
    
@dataclass(frozen=True)
class FindAndReplaceAction(Action):
    path: str
    find_text: str
    replace_text:str

    def key(self):
        return "FIND_AND_REPLACE"
    
    def short_string(self) -> str:
        return f"Find and replace `{self.find_text}` with `{self.replace_text}` in `{self.path}`."
    
    def run(self) -> str:
        with io.open(self.path, mode="r", encoding="utf-8") as file:
            content = file.read()
        new_content = content.replace(self.find_text, self.replace_text, 1)
        if new_content == content:
            return f"FindAndReplaceAction failed: The string '{self.find_text}' to be replaced was not found in the file."
        with io.open(self.path, mode="w", encoding="utf-8") as file:
            file.write(new_content)
        print(f"FindAndReplaceAction RESULT: Replaced `{self.find_text}` with `{self.replace_text}` in `{self.path}`.")
        return "FindAndReplaceAction Successfully replaced text."

    


@dataclass(frozen=True)
class FileEntry:
    name: str
    is_directory: bool
    size: int
    creation_time: float
    modification_time: float

    def __str__(self) -> str:
        file_type = "Directory" if self.is_directory else "File"
        return f"{file_type}: {self.name} | Size: {self.size} bytes | Created: {self.creation_time} | Modified: {self.modification_time}"

@dataclass(frozen=True)
class ListDirectoryAction(Action):
    path: str

    def key(self):
        return "LIST_DIRECTORY"

    def short_string(self) -> str:
        return f"List directory `{self.path}`."

    def get_file_info(self, file_path: str) -> FileEntry:
        st = os.stat(file_path)
        return FileEntry(
            name=os.path.basename(file_path),
            is_directory=stat.S_ISDIR(st.st_mode),
            size=st.st_size,
            creation_time=st.st_ctime,
            modification_time=st.st_mtime,
        )

    def run(self) -> str:
        if os.path.exists(self.path):
            contents = os.listdir(self.path)
            file_entries = [self.get_file_info(os.path.join(self.path, entry)) for entry in contents]
            formatted_entries = "\n".join(str(entry) for entry in file_entries)
            return formatted_entries
        else:
            print(f"ListDirectoryAction RESULT: Failed to list directory `{self.path}`.")
            return f"ListDirectoryAction Failed to list directory `{self.path}`."

class Memory:
    def __init__(self):
        self.storage = dict()

    def set(self, key: str, value: str):
        self.storage[key] = value

    def get(self, key: str):
        return self.storage.get(key)

mem = Memory()

@dataclass(frozen=True)
class KVSetAction(Action):
    memkey: str
    memval: str

    def key(self) -> str:
        return "KV_SET"

    def short_string(self) -> str:
        return f"Set memory key `{self.memkey}` to value `{self.memval}`."

    def run(self) -> str:
        mem.set(self.memkey, self.memval)
        return f"KVSetAction: Set key `{self.memkey}` to value `{self.memval}`."


@dataclass(frozen=True)
class KVGetAction(Action):
    memkey: str

    def key(self) -> str:
        return "KV_GET"

    def short_string(self) -> str:
        return f"Get memory value for key `{self.memkey}`."

    def run(self) -> str:
        value = mem.get(self.memkey)
        if value is not None:
            return f"KVGetAction: Retrieved value `{value}` for key `{self.memkey}`."
        else:
            return f"KVGetAction: Key `{self.memkey}` not found in memory."
        

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
    TellUserAction,
    ReadFileAction,
    WriteFileAction,
    AppendFileAction,
    RunPythonAction,
    SearchOnlineAction,
    ExtractInfoAction,
    FindAndReplaceAction,
    ListDirectoryAction,
    ShutdownAction,
    CreateDirectoryAction,
    KVGetAction,
    KVSetAction,
])