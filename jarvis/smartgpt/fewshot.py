import os

from jarvis.smartgpt import utils

# Initialize the singleton to None
_examples_db = None


def init():
    global _examples_db
    example_dir_path = os.path.join(os.getcwd(), "data/examples")

    # Check if example_dir_path exists
    if not os.path.exists(example_dir_path):
        raise FileNotFoundError(f"The directory '{example_dir_path}' does not exist.")

    if _examples_db is None:
        _examples_db = utils.DB(example_dir_path)


def get(example_name: str):
    if _examples_db is None:
        raise RuntimeError("Examples database not initialized")
    return _examples_db.get(example_name, "")
