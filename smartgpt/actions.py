
from dataclasses import dataclass
import io
import subprocess
import inspect
import json
from typing import Union
from abc import ABC


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
class RunPythonAction(Action):
    path: str
    timeout: int  # Add the timeout parameter (in seconds)
    code:str

    def key(self) -> str:
        return "RUN_PYTHON"

    def short_string(self) -> str:
        return f"Run Python file `{self.path}`."

    def run(self) -> str:
        # write code to path and run
        with io.open(self.path, mode="w", encoding="utf-8") as file:
            file.write(self.code)
        with subprocess.Popen(
            f"python {self.path}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        ) as process:
            try:
                exit_code = process.wait(timeout=self.timeout)  # Add the timeout argument
                output = process.stdout.read() if process.stdout else ""
                output = f"\nPython script at `{self.path}` returned exit code {exit_code}, content:\n{output}"
                if exit_code != 0:
                    output += f"\n\nPython script code:\n{self.code}"
                print(output)
                return output
            except subprocess.TimeoutExpired:
                process.kill()
                return f"RunPythonAction failed: The Python script at `{self.path}` timed out after {self.timeout} seconds."


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
])