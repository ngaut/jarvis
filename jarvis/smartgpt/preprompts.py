import os

from jarvis.smartgpt import utils

# Initialize the singleton to None
_prompts_db = None


def init():
    global _prompts_db
    prompt_dir_path = os.path.join(os.getcwd(), "data/prompts")

    # Check if prompt_dir_path exists
    if not os.path.exists(prompt_dir_path):
        raise FileNotFoundError(f"The directory '{prompt_dir_path}' does not exist.")

    if _prompts_db is None:
        _prompts_db = utils.DB(prompt_dir_path)


def get(prompt_name: str):
    if _prompts_db is None:
        raise RuntimeError("Prompts database not initialized")
    return _prompts_db.get(prompt_name, "")
