from typing import List, Dict, Tuple
from abc import ABC, abstractmethod

import yaml

from smartgpt import gpt
from smartgpt import utils
from smartgpt import preprompts


class Reviewer(ABC):
    def __init__(self, model):
        self.model = model

    @abstractmethod
    def review(self, resp_instructions: str) -> Tuple[str, List[Dict]]:
        pass

    def buildSystemMessages(self) -> List[Dict]:
        messages = []
        messages.append({"role": "system", "content": preprompts.get('reviewer_sys')})
        messages.append({"role": "user", "content": preprompts.get('jvm_spec')})
        return messages

    def buildReviewContent(self, resp_instructions: str) -> str:
        review_content = preprompts.get("reviewer_content").format(
            instructions = resp_instructions
        )
        return review_content

class EvalSyntaxReviewer(Reviewer):
    def review(self, resp_instructions: str) -> Tuple[str, List[Dict]]:
        messages = self.buildSystemMessages()
        messages.append({"role": "user", "content": self.buildReviewContent(resp_instructions)})
        messages.append({"role": "user", "content": preprompts.get('reviewer_eval_syntax')})

        review_response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": review_response})

        review_response = utils.strip_yaml(review_response)
        result = yaml.safe_load(review_response)

        if result.get("approved", False):
            return resp_instructions, messages
        else:
            if "revised_version" in result:
                return result.get("revised_version"), messages
            else:
                return resp_instructions, messages

class LoopIndexKeyReviewer(Reviewer):
    def review(self, resp_instructions: str) -> Tuple[str, List[Dict]]:
        messages = self.buildSystemMessages()
        messages.append({"role": "user", "content": self.buildReviewContent(resp_instructions)})
        messages.append({"role": "user", "content": preprompts.get('reviewer_index_key')})

        review_response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": review_response})

        review_response = utils.strip_yaml(review_response)
        result = yaml.safe_load(review_response)

        if result.get("approved", False):
            return resp_instructions, messages
        else:
            if "revised_version" in result:
                return result.get("revised_version"), messages
            else:
                return resp_instructions, messages
