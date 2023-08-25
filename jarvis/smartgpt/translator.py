import logging
from typing import List, Dict, Any

from jarvis.smartgpt import gpt
from jarvis.smartgpt import utils
from jarvis.smartgpt import fewshot
from jarvis.smartgpt import preprompts
from jarvis.smartgpt import reviewer
from jarvis.utils.tracer import conditional_chan_traceable

REVIEWER_CLASSES = [
    (reviewer.EvalSyntaxReviewer, [gpt.GPT_3_5_TURBO_16K]),
    (reviewer.LoopIndexKeyReviewer, [gpt.GPT_3_5_TURBO_16K]),
]

REVIEWER_GPT4_CLASSES = [
    (reviewer.SyntaxReviewer, [gpt.GPT_4]),
    (reviewer.SimulationReviewer, [gpt.GPT_4]),
]

FEW_SHOT_EXAMPLE = "4"

class Translator:
    def __init__(self, model):
        self.model = model
        self.reviewers = [cls(*params) for cls, params in REVIEWER_GPT4_CLASSES]

    def build_system_prompt(self) -> List[Dict]:
        messages = []
        messages.append({"role": "system", "content": preprompts.get("translator_sys") + "\n" + fewshot.get(FEW_SHOT_EXAMPLE)})
        return messages

    def prepare_user_hints(self, task_info: Dict[str, Any]):
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
        return hints

    def revise_instructions(self, task_info: Dict[str, Any], instrs, review_results, review_comments):
        review_feedbacks = []
        for i, (result, comment) in enumerate(zip(review_results, review_comments)):
            if result is False:
                review_feedbacks.append(comment)

        if len(review_feedbacks) == 0:
            logging.info("No revision required.")
            return instrs

        messages = []
        messages.append({"role": "system", "content": preprompts.get("reviser_sys")})
        messages.append({"role": "user", "content": preprompts.get("reviser_user").format(
            instructions = instrs,
            review_feedback="\n\n".join(review_feedbacks),
        )})

        resp = gpt.send_messages(messages, self.model)
        messages.append({"role": "asssistant", "content": resp})
        self._trace_reviser_gen(task_info, messages)

        return utils.strip_yaml(resp)

    @conditional_chan_traceable(run_type="chain")
    def translate_to_instructions(self, task_info: Dict[str, Any]):
        hints = self.prepare_user_hints(task_info)
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

        review_results = []
        review_comments = []
        for rv in self.reviewers:
            result, comment, messages = rv.review(resp)
            self._trace_reviewer_gen(task_info, rv, messages)
            review_results.append(result)
            review_comments.append(comment)

        return self.revise_instructions(task_info, resp, review_results, review_comments)

    def _trace_llm_gen(self, task_info, messages):
        with open(f"review_{task_info.get('task_num', 0)}.txt", "w") as f:
            for msg in messages:
                f.write(f"{msg['role'].upper()}:\n")
                f.write(f"{msg['content']}\n\n")

    def _trace_reviewer_gen(self, task_info, rv, messages):
        with open(f"review_{task_info.get('task_num', 0)}.txt", "a") as f:
            f.write("=============================================\n")
            f.write(f"Reviewer: {rv.__class__.__name__}\n")
            f.write("=============================================\n")
            for msg in messages:
                f.write(f"{msg['role'].upper()}:\n")
                f.write(f"{msg['content']}\n\n")

    def _trace_reviser_gen(self, task_info, messages):
        with open(f"review_{task_info.get('task_num', 0)}.txt", "a") as f:
            f.write("=============================================\n")
            f.write("Reviser\n")
            f.write("=============================================\n")
            for msg in messages:
                f.write(f"{msg['role'].upper()}:\n")
                f.write(f"{msg['content']}\n\n")
