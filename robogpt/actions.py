
from dataclasses import dataclass
import os
import io
import subprocess
from spinner import Spinner
import gpt
import requests
from bs4 import BeautifulSoup
from googlesearch import search
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager


@dataclass(frozen=True)
class Action:
    def key(self) -> str:
        raise NotImplementedError

    def short_string(self) -> str:
        raise NotImplementedError

    def run(self) -> str:
        """Returns what RoboGPT should learn from running the action."""
        raise NotImplementedError


@dataclass(frozen=True)
class TellUserAction(Action):
    message: str

    def key(self) -> str:
        return "TELL_USER"

    def short_string(self) -> str:
        return f'Tell user "{self.message}".'

    def run(self) -> str:
        return f"Told user the following: {self.message}"


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
                print(f"ReadFileAction RESULT: Read file `{self.path}`.")
                return contents
        else:
            # Check if the path is a remote file
            try:
                response = requests.get(self.path)
                response.raise_for_status()
                contents = response.text
                print(f"ReadFileAction RESULT: Read remote file `{self.path}`.")
                return contents
            except requests.exceptions.HTTPError as e:
                print(f"ReadFileAction RESULT: Failed to read file `{self.path}`: {e}")
                return f"ReadFileAction Failed to read file `{self.path}`: {e}"


@dataclass(frozen=True)
class WriteFileAction(Action):
    path: str
    content: str

    def key(self) -> str:
        return "WRITE_FILE"

    def short_string(self) -> str:
        return f"Write file `{self.path}`."

    def run(self) -> str:
        with io.open(self.path, mode="w", encoding="utf-8") as file:
            file.write(self.content)
            print(f"WriteFileAction RESULT: Wrote file `{self.path}`.")
            return "WriteFileAction File successfully written."


@dataclass(frozen=True)
class AppendFileAction(Action):
    path: str
    content: str

    def key(self) -> str:
        return "APPEND_FILE"

    def short_string(self) -> str:
        return f"Append file `{self.path}`."

    def run(self) -> str:
        with io.open(self.path, mode="a", encoding="utf-8") as file:
            file.write(self.content)
            print(f"AppendFileAction RESULT: Appended file `{self.path}`.")
            return "AppendFileAction File successfully appended."

@dataclass(frozen=True)
class CreateDirectoryAction(Action):
    path: str

    def key(self) -> str:
        return "CREATE_DIRECTORY"

    def short_string(self) -> str:
        return f"Create directory `{self.path}`."

    def run(self) -> str:
        os.makedirs(self.path)
        print(f"CreateDirectoryAction RESULT: Created directory `{self.path}`.")
        return "CreateDirectoryAction Directory successfully created."


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
            extracted_info = gpt.send_message(messages, max_response_token_count)
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
    reason: str

    def key(self):
        return "SHUTDOWN"

    def short_string(self) -> str:
        return "Shutdown."

    def run(self) -> str:
        # This action is treated specially, so this can remain unimplemented.
        raise NotImplementedError
    
@dataclass(frozen=True)
class FindAndReplaceAction(Action):
    path: str
    find: str
    replace:str

    def key(self):
        return "FIND_AND_REPLACE"
    
    def short_string(self) -> str:
        return f"Find and replace `{self.find}` with `{self.replace}` in `{self.path}`."
    
    def run(self) -> str:
        with io.open(self.path, mode="r", encoding="utf-8") as file:
            content = file.read()
        new_content = content.replace(self.find, self.replace)
        if new_content == content:
            return f"FindAndReplaceAction failed: The string '{self.find}' to be replaced was not found in the file."
        with io.open(self.path, mode="w", encoding="utf-8") as file:
            file.write(new_content)
        print(f"FindAndReplaceAction RESULT: Replaced `{self.find}` with `{self.replace}` in `{self.path}`.")
        return "FindAndReplaceAction Successfully replaced text."

    

@dataclass(frozen=True)
class ListDirectoryAction(Action):
    path: str

    def key(self):
        return "LIST_DIRECTORY"

    def short_string(self) -> str:
        return f"List directory `{self.path}`."

    def run(self) -> str:
        if os.path.exists(self.path):
            contents = os.listdir(self.path)
            print(f"ListDirectoryAction RESULT: Listed directory `{self.path}`.")
            return "\n".join(contents)
        else:
            print(f"ListDirectoryAction RESULT: Failed to list directory `{self.path}`.")
            return f"ListDirectoryAction Failed to list directory `{self.path}`."