import logging
import re
from typing import List, Dict, Tuple
from abc import ABC, abstractmethod

import yaml

from jarvis.smartgpt import gpt
from jarvis.smartgpt import utils
from jarvis.smartgpt import preprompts


REVIEW_REPEATED_COUNT = 1

class Reviewer(ABC):
    def __init__(self, model):
        self.model = model

    @abstractmethod
    def review(self, instrs: str) -> Tuple[bool, str, List[Dict]]:
        pass

    def buildSystemMessages(self) -> List[Dict]:
        messages = []
        prompt = preprompts.get('reviewer_sys') + "\n" + preprompts.get('jvm_spec')
        messages.append({"role": "system", "content": prompt})
        return messages

    def generalReview(self, instrs: str, review_prompt: str) -> Tuple[bool, str, List[Dict]]:
        messages = self.buildSystemMessages()

        review_content = preprompts.get(review_prompt).format(
            instructions = '\n'.join('  ' + line for line in instrs.splitlines())
        )
        messages.append({"role": "user", "content": review_content})

        review_response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": review_response})

        review_response = utils.strip_yaml(review_response)
        result = yaml.safe_load(review_response)

        if result.get("approved", True):
            return True, "", messages
        else:
            if "review_comment" in result:
                return False, result.get("review_comment"), messages
            else:
                return True, "", messages


class EvalSyntaxReviewer(Reviewer):
    def review(self, instrs: str) -> Tuple[bool, str, List[Dict]]:
        return self.generalReview(instrs, "reviewer_eval_syntax")


class LoopIndexKeyReviewer(Reviewer):
    def review(self, instrs: str) -> Tuple[bool, str, List[Dict]]:
        return self.generalReview(instrs, "reviewer_index_key")


class SimulationReviewer(Reviewer):
    def review(self, instrs: str) -> Tuple[bool, str, List[Dict]]:
        return self._review(instrs, REVIEW_REPEATED_COUNT)

    def _review(self, instrs: str, count: int) -> Tuple[bool, str, List[Dict]]:
        messages = []
        messages.append({"role": "system", "content": preprompts.get("reviewer_simulation_sys")})

        review_content = preprompts.get("reviewer_simulation_user").format(
            instructions = instrs
        )
        messages.append({"role": "user", "content": review_content})

        response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": response})

        messages.append({"role": "user", "content": preprompts.get("reviewer_simulation_output")})
        response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": response})

        if "CORRECT!" in response:
            logging.info(f"The #{REVIEW_REPEATED_COUNT - count + 1}/{REVIEW_REPEATED_COUNT} round review of Simulation Reviewer says LGTM.")
            if count - 1 == 0:
                return True, "", messages
            return self._review(instrs, count - 1)

        match = re.search(r'\"{3}(.*?)\"{3}', response, re.DOTALL)
        if match:
            extracted_text = match.group(1).strip()
        else:
            logging.info("No feedback text found between triple quotes.")
            return True, "", messages

        review_feedback = f"The Simulation Reviewer's feedback:\n\"\"\"{extracted_text}\"\"\""
        logging.info(review_feedback)
        return False, review_feedback, messages


class SyntaxReviewer(Reviewer):
    def review(self, instrs: str) -> Tuple[bool, str, List[Dict]]:
        messages = []
        messages.append({"role": "system", "content": preprompts.get("reviewer_syntax_sys")})
        messages.append({"role": "user", "content": preprompts.get("reviewer_syntax_user").format(
            instructions = instrs
        )})

        resp = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": resp})

        if "CORRECT!" in resp:
            logging.info("Syntax Reviewer says LGTM.")
            return True, "", messages

        match = re.search(r'\"{3}(.*?)\"{3}', resp, re.DOTALL)
        if match:
            extracted_text = match.group(1).strip()
        else:
            logging.info("No feedback text found between triple quotes.")
            return True, "", messages

        review_feedback = f"The Syntax Reviewer's feedback:\n\"\"\"{extracted_text}\"\"\""
        logging.info(review_feedback)
        return False, review_feedback, messages
