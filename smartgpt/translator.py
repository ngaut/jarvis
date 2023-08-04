import logging
from typing import List, Dict, Any

from smartgpt import gpt
from smartgpt import utils
from smartgpt import fewshot
from smartgpt import preprompts
from smartgpt import reviewer


REVIEWER_CLASSES = [
    (reviewer.EvalSyntaxReviewer, [gpt.GPT_3_5_TURBO_16K]),
    (reviewer.LoopIndexKeyReviewer, [gpt.GPT_3_5_TURBO_16K])]

FEW_SHOT_EXAMPLE = "3"

class Translator:
    def __init__(self, model):
        self.model = model
        self.reviewers = [cls(*params) for cls, params in REVIEWER_CLASSES]

    def build_system_prompt(self) -> List[Dict]:
        messages = []
        messages.append({"role": "system", "content": preprompts.get("translator_sys")})
        messages.append({"role": "user", "content": fewshot.get(FEW_SHOT_EXAMPLE)})
        return messages

    def translate_to_instructions(self, task_info: Dict[str, Any]):
        previous_task_outcomes = ""
        if task_info.get("first_task", False):
            previous_task_outcomes += "This is the first task, so there are no previous tasks or outcomes."
        else:
            for item in task_info.get("previous_outcomes", []):
                previous_task_outcomes += f"\n  - {item.get('outcome')}"

        hints = ""
        for item in task_info.get("hints", []):
            hints += f"\n  - {item}"
        if not hints:
            hints = "[]"

        user_prompt = preprompts.get("translator_user").format(
            task = task_info.get("task", ""),
            start_seq = task_info.get("start_seq", ""),
            hints = hints,
            previous_task_outcomes = previous_task_outcomes,
        )
        logging.info(f"User Prompt: \n{user_prompt}")

        messages = self.build_system_prompt()
        messages.append({"role": "user", "content": user_prompt})

        resp = gpt.send_messages(messages, self.model)
        messages.append({"role": "asssistant", "content": resp})
        self._trace_llm_gen(task_info, messages)

        resp = utils.strip_yaml(resp)
        logging.info(f"LLM Response: \n{resp}")

        for rev in self.reviewers:
            resp, messages = rev.review(resp)
            self._trace_reviewer_gen(task_info, rev, messages)

        return resp

    def _trace_llm_gen(self, task_info, messages):
        with open(f"review_{task_info.get('task_num', 0)}.txt", "w") as f:
            for msg in messages:
                f.write(f"{msg['role'].upper()}:\n")
                f.write(f"{msg['content']}\n\n")


    def _trace_reviewer_gen(self, task_info, rev, messages):
        with open(f"review_{task_info.get('task_num', 0)}.txt", "a") as f:
            f.write("=============================================\n")
            f.write(f"Reviewer: {rev.__class__.__name__}\n")
            f.write("=============================================\n")
            for msg in messages:
                f.write(f"{msg['role'].upper()}:\n")
                f.write(f"{msg['content']}\n\n")
