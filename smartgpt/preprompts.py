import os
from pathlib import Path


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

# Initialize the singleton to None
_prompts_db = None

def load(prompt_dir: str):
    global _prompts_db
    prompt_dir_path = os.path.join(os.getcwd(), prompt_dir)
    if _prompts_db is None:
        _prompts_db = DB(prompt_dir_path)

def get(prompt_name: str):
    if _prompts_db is None:
        raise RuntimeError("Prompts database not initialized")
    return _prompts_db.get(prompt_name, "")
