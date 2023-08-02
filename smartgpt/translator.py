import logging
from typing import Dict, Any

from smartgpt import gpt
from smartgpt import utils
from smartgpt import fewshot
from smartgpt import preprompts
from smartgpt import reviewer


FEW_SHOT_EXAMPLE = "3"
REVIEWER_CLASSES = [(reviewer.EvalSyntaxReviewer, [gpt.GPT_3_5_TURBO_16K])]

class Translator:
    def __init__(self, model):
        self.model = model
        self.reviewers = [cls(*params) for cls, params in REVIEWER_CLASSES]


    def generate_system_prompt(self) -> str:
        system_prompt = preprompts.get("translator_sys")
        fewshot_example = fewshot.get(FEW_SHOT_EXAMPLE)
        return system_prompt + "\n" + fewshot_example


    def translate_to_instructions(self, task_info: Dict[str, Any]):
        previous_task_outcomes = ""
        if task_info.get("first_task", False):
            previous_task_outcomes += "* This is the first task, so there are no previous tasks or outcomes.\n"
        else:
            for item in task_info.get("previous_outcomes", []):
                previous_task_outcomes += f"* {item['outcome']}\n"

        hints = ""
        for item in task_info.get("hints", []):
            hints += f"* {item}\n"
        if not hints:
            hints = "No hints\n"

        system_prompt = self.generate_system_prompt()
        user_prompt = preprompts.get("translator_user").format(
            task = task_info.get("task", ""),
            start_seq = task_info.get("start_seq", ""),
            hints = hints,
            previous_task_outcomes = previous_task_outcomes,
        )

        logging.info(f"User Prompt:\n{user_prompt}")

        resp = gpt.complete(prompt=user_prompt, model=self.model, system_prompt=system_prompt)
        resp = utils.strip_yaml(resp)

        self._trace_llm_gen(task_info, system_prompt, user_prompt, resp)
        logging.info(f"LLM Response: \n{resp}")

        for rev in self.reviewers:
            resp, messages = rev.review(resp)
            self._trace_reviewer_gen(task_info, rev, messages)

        return resp


    def _trace_llm_gen(self, task_info, system_prompt, user_prompt, llm_resp):
        num = task_info.get("task_num", 0)
        with open(f"review_{num}.txt", "w") as f:
            f.write(f"System Prompt:\n{system_prompt}\n\n")
            f.write(f"User Prompt:\n{user_prompt}\n\n")
            f.write(f"LLM Response:\n{llm_resp}\n\n")


    def _trace_reviewer_gen(self, task_info, rev, messages):
        num = task_info.get("task_num", 0)
        with open(f"review_{num}.txt", "a") as f:
            f.write("=============================================\n")
            f.write(f"Reviewer: {rev.__class__.__name__}\n")
            f.write("=============================================\n")
            for msg in messages:
                f.write(f"{msg['role'].upper()}:\n")
                f.write(f"{msg['content']}\n\n")
