from typing import List, Dict, Tuple
from abc import ABC, abstractmethod

from smartgpt import gpt
from smartgpt import utils
from smartgpt import preprompts


class Reviewer(ABC):
    def __init__(self, model):
        self.model = model

    @abstractmethod
    def review(self, instructions: str) -> Tuple[str, List[Dict]]:
        pass

class EvalSyntaxReviewer(Reviewer):
    def review(self, instructions: str) -> Tuple[str, List[Dict]]:
        messages = []
        messages.append({"role": "system", "content": preprompts.get('reviewer_sys')})
        messages.append({"role": "user", "content": preprompts.get('jvm_spec')})
        messages.append({"role": "user", "content": f"JVM Instructions (pending review):\n{instructions}"})
        messages.append({"role": "user", "content": preprompts.get('reviewer_eval_syntax')})

        review_response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": review_response})

        if review_response.lower() == "approved":
            return instructions, messages
        else:
            review_response = utils.strip_yaml(review_response)
            return review_response, messages
