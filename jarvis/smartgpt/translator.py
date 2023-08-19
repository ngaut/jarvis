import logging
from typing import List, Dict, Any

from jarvis.smartgpt import gpt
from jarvis.smartgpt import utils
from jarvis.smartgpt import fewshot
from jarvis.smartgpt import preprompts
from jarvis.smartgpt import reviewer


REVIEWER_CLASSES = [
    (reviewer.EvalSyntaxReviewer, [gpt.GPT_3_5_TURBO_16K]),
    (reviewer.LoopIndexKeyReviewer, [gpt.GPT_3_5_TURBO_16K])]

REVIEWER_GPT4_CLASSES = [(reviewer.SimulationReviewer, [gpt.GPT_4])]

FEW_SHOT_EXAMPLE = "3"

class Translator:
    def __init__(self, model):
        self.model = model
        self.reviewers = [cls(*params) for cls, params in REVIEWER_GPT4_CLASSES]

    def build_system_prompt(self) -> List[Dict]:
        messages = []
        messages.append({"role": "system", "content": preprompts.get("translator_sys") + "\n" + fewshot.get(FEW_SHOT_EXAMPLE)})
        return messages

    def translate_to_instructions(self, task_info: Dict[str, Any]):
        hints = ""
        if task_info.get("first_task", False):
            hints = "\n  - \"This is the first task, so there are no previous tasks or outcomes.\""
        else:
            for item in task_info.get("previous_outcomes", []):
                hints += f"\n  - \"This is the #{task_info.get('task_num')} task, the previous task #{item.get('task_num')} has outcome: {item.get('outcome')}\""

        if task_info.get("goal", ""):
            hints += f"\n  - \"The user's original request: {task_info.get('goal')}\""

        for item in task_info.get("hints", []):
            hints += f"\n  - \"{item}\""

        if not hints:
            hints = "[]"

        user_prompt = preprompts.get("translator_user").format(
            task_num=task_info.get("task_num", 0),
            task = f"\"{task_info.get('task', '')}\"",
            objective = f"\"{task_info.get('objective', '')}\"",
            start_seq = task_info.get("start_seq", ""),
            hints = hints,
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
