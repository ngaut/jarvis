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
        system_prompt = preprompts.get("translator_sys")
        few_shot_example = examples.get_example(example)
        return system_prompt + few_shot_example


    def translate_to_instructions(self, task_info: Dict[str, Any]):
        previous_task_outcomes = ""
        if task_info["first_task"]:
            previous_task_outcomes += "* This is the first task, so there are no previous tasks or outcomes.\n"
        else:
            for item in task_info.get("previous_outcomes", []):
                previous_task_outcomes += f"* {item['outcome']}\n"

        hints = ""
        for item in task_info.get("hints", []):
            hints += f"* {item}\n"
        if hints == "":
            hints = "No hints\n"

        user_prompt = preprompts.get("translator_user").format(
            task = task_info["task"],
            start_seq = task_info["start_seq"],
            hints = hints,
            previous_task_outcomes = previous_task_outcomes,
        )

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
