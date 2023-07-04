import os
from typing import List

from smartgpt import actions
from smartgpt import jvm
from smartgpt import planner
from smartgpt import gpt

jvm.load_kv_store()
actions.load_cache()

def execute_task(objective: str, task: str, context: List[dict]) -> str:
    os.makedirs("workspace", exist_ok=True)
    os.chdir("workspace")
    return ""