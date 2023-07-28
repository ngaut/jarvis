# Description: Utility functions
from pathlib import Path

from smartgpt import jvm


def wrap_string_to_eval(text):
    return jvm.LAZY_EVAL_PREFIX + text + ")"

def strip_yaml(text):
    # Strip whitespace (including newline) from end
    text = text.rstrip()

    # keep removing the last "```" if it exists
    while text.endswith("```"):
        text = text[:-3]
        text = text.rstrip()

    # if text starts with "```yaml\n", remove it
    if text.startswith("```yaml\n"):
        text = text[8:]

    return text

def sys_eval(text):
    return eval(text)

def str_to_bool(s):
    if isinstance(s, bool):
        return s
    elif isinstance(s, str):
        return s.lower() == 'true'
    else:
        return False


class DB:
    """A simple key-value store, where keys are filenames and values are file contents."""

    def __init__(self, path):
        self.path = Path(path).absolute()
        self.path.mkdir(parents=True, exist_ok=True)

    def __contains__(self, key):
        return (self.path / key).is_file()

    def __getitem__(self, key):
        full_path = self.path / key

        if not full_path.is_file():
            raise KeyError(f"File '{key}' could not be found in '{self.path}'")
        with full_path.open("r", encoding="utf-8") as f:
            return f.read()

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key, val):
        full_path = self.path / key
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(val, str):
            full_path.write_text(val, encoding="utf-8")
        else:
            # If val is neither a string nor bytes, raise an error.
            raise TypeError("val must be either a str or bytes")
