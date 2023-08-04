import os

from smartgpt import utils

# Initialize the singleton to None
_prompts_db = None

def initialize(prompt_dir: str):
    global _prompts_db
    prompt_dir_path = os.path.join(os.getcwd(), prompt_dir)
    if _prompts_db is None:
        _prompts_db = utils.DB(prompt_dir_path)

def get(prompt_name: str):
    if _prompts_db is None:
        raise RuntimeError("Prompts database not initialized")
    return _prompts_db.get(prompt_name, "")
