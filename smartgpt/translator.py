import json
import logging
from typing import Dict, Any

from smartgpt import gpt
from smartgpt import utils
from smartgpt import examples
from smartgpt import preprompts

FEW_SHOT_EXAMPLE = "example3"

class Translator:
    def __init__(self, model):
        self.model = model
        self.messages = []
        self.task_info = {}

    def generate_system_prompt(self, example: str) -> str:
        few_shot_example = examples.get_example(example)
        system_prompt = preprompts.get("translator_sys_prompt")
        return system_prompt + few_shot_example


    def translate_to_instructions(self, task_info: Dict[str, Any]):
        hints = ""
        if task_info["first_task"]:
            hints += "This is the first task, so there are no previous tasks or outcomes.\n"
        else:
            for item in task_info.get("previous_outcomes", []):
                hints += f"{item['outcome']}\n"

        for item in task_info.get("hints", []):
            hints += f"{json.dumps(item)}\n"

        user_prompt = (
            f"Your task: {json.dumps(task_info['task'])}\n"
            f"The starting sequence: {json.dumps(task_info['start_seq'])}\n"
            "You are going to create a series of JVM instructions to complete your task.\n"
            "Ensure you fully utilize the outcomes of previous tasks in user hints.\n"
            "Remember: Every instruction must save its outcome to the database so it can be used in subsequent tasks.\n\n"
        )

        if hints != "":
            user_prompt += f"Here are some hints from user:\n{hints}\n"

        user_prompt += "Please provide your response in YAML format:\n```yaml\n"

        logging.info(f"User Prompt:\n{user_prompt}")

        #logging.info(f"================================================")
        #logging.info(f"Translate task: {task_info}")
        #logging.info(f"================================================")

        system_prompt = self.generate_system_prompt(FEW_SHOT_EXAMPLE)
        resp = gpt.complete(prompt=user_prompt, model=self.model, system_prompt=system_prompt)
        self.trace_llm_completion(system_prompt, user_prompt, resp, task_info)

        resp = utils.strip_yaml(resp)
        logging.info(f"LLM Response: \n{resp}")
        return resp

    def trace_llm_completion(self, system_prompt: str, user_prompt: str, response: str, task_info: Dict[str, Any]):
        self.messages = []
        self.messages.append({"role": "system", "content": system_prompt})
        self.messages.append({"role": "user", "content": user_prompt})
        self.messages.append({"role": "assistant", "content": response})

        self.task_info = task_info
