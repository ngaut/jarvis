from typing import List, Dict, Tuple
from abc import ABC, abstractmethod

import yaml

from jarvis.smartgpt import gpt
from jarvis.smartgpt import utils
from jarvis.smartgpt import preprompts


class Reviewer(ABC):
    def __init__(self, model):
        self.model = model

    @abstractmethod
    def review(self, resp_instructions: str) -> Tuple[str, List[Dict]]:
        pass

    def buildSystemMessages(self) -> List[Dict]:
        messages = []
        prompt = preprompts.get('reviewer_sys') + "\n" + preprompts.get('jvm_spec')
        messages.append({"role": "system", "content": prompt})
        return messages

    def generalReview(self, resp_instructions: str, review_prompt: str) -> Tuple[str, List[Dict]]:
        messages = self.buildSystemMessages()

        review_content = preprompts.get(review_prompt).format(
            instructions = '\n'.join('  ' + line for line in resp_instructions.splitlines())
        )
        messages.append({"role": "user", "content": review_content})

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


class EvalSyntaxReviewer(Reviewer):
    def review(self, resp_instructions: str) -> Tuple[str, List[Dict]]:
        return self.generalReview(resp_instructions, "reviewer_eval_syntax")

class LoopIndexKeyReviewer(Reviewer):
    def review(self, resp_instructions: str) -> Tuple[str, List[Dict]]:
        return self.generalReview(resp_instructions, "reviewer_index_key")
