import os

from smartgpt import utils

# Initialize the singleton to None
_examples_db = None

def initialize(example_dir: str):
    global _examples_db
    example_dir_path = os.path.join(os.getcwd(), example_dir)
    if _examples_db is None:
        _examples_db = utils.DB(example_dir_path)

def get(example_name: str):
    if _examples_db is None:
        raise RuntimeError("Examples database not initialized")
    return _examples_db.get(example_name, "")
