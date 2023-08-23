import logging
import re
from typing import List, Dict, Tuple
from abc import ABC, abstractmethod

import yaml

from jarvis.smartgpt import gpt
from jarvis.smartgpt import utils
from jarvis.smartgpt import preprompts
from jarvis.smartgpt import fewshot


REVIEW_REPEATED_COUNT = 2

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

        if result.get("approved", True):
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

class SimulationReviewer(Reviewer):
    def review(self, resp_instructions: str) -> Tuple[str, List[Dict]]:
        return self._review(resp_instructions, REVIEW_REPEATED_COUNT)

    def _review(self, resp_instructions: str, count: int) -> Tuple[str, List[Dict]]:
        messages = []
        messages.append({"role": "system", "content": preprompts.get("reviewer_simulation_sys")})

        review_content = preprompts.get("reviewer_simulation_user").format(
            instructions = resp_instructions
        )
        messages.append({"role": "user", "content": review_content})

        response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": response})

        messages.append({"role": "user", "content": preprompts.get("reviewer_simulation_output")})
        response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": response})

        match_answer = re.match(r'(yes|no)', response.lower())
        is_need_regenerate = match_answer.group(1) if match_answer else 'no'

        if is_need_regenerate == 'no':
            logging.info(f"The #{REVIEW_REPEATED_COUNT - count + 1}/{REVIEW_REPEATED_COUNT} round simulation review says LGTM.")
            if count - 1 == 0:
                return resp_instructions, messages
            return self._review(resp_instructions, count - 1)

        logging.info(f"The #{REVIEW_REPEATED_COUNT - count + 1}/{REVIEW_REPEATED_COUNT} round simulation review failed, start regenerating ...")

        messages.append({"role": "user", "content": preprompts.get("reviewer_simulation_regenerate")})
        response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": response})

        pattern = r'```\s*(?:[a-zA-Z]+\s*)?\n(.*?)\s*```'
        match_code = re.search(pattern, response, re.DOTALL)
        revised_instructions = match_code.group(1) if match_code else None

        if revised_instructions:
            return revised_instructions, messages
        return resp_instructions, messages
