from typing import List, Dict
from copy import deepcopy
import json

from smartgpt import gpt


class Reviewer:
    def __init__(self, model):
        self.model = model

    def review_plan_gen(self, messages: List[Dict]) -> Dict:
        review_prompt = """
Please review the prompt and your response, then answer the following questions in the provided format:
{
    "ambiguity_in_prompt": If there's no ambiguity in the prompt, write 'none'. If there is, please list the ambiguous elements.
    "not_self_contained_tasks": If there's a task description that isn't self-contained enough, please list it. If all are self-contained, write 'none'.
    "achieve_goal": Can the generated task lists meet the user's goal? true or false.
}
"""

        # Construct the messages for the review request
        messages = deepcopy(messages)
        messages.append({"role": "user", "content": review_prompt})

        # Send the review request to the LLM
        review_response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": review_response})

        # write to files
        self._trace_llm_gen("plan", messages)
        return json.loads(review_response)


    def review_instructions_gen(self, step, messages: List[Dict]) -> Dict:
        review_prompt = """
Please review the prompt and your response, then answer the following questions in the provided format:
{
    "ambiguity_in_prompt": If there's no ambiguity in the prompt, write 'none'. If there is, please list the ambiguous elements.
    "bad_instructions": If there's a instruction description that isn't self-contained enough, please list it. If all are self-contained, write 'none'.
    "achieve_goal": Can the generated instruction list meet the task's objective? true or false.
}
"""

        # Construct the messages for the review request
        messages = deepcopy(messages)
        messages.append({"role": "user", "content": review_prompt})

        # Send the review request to the AI model
        review_response = gpt.send_messages(messages, self.model)
        messages.append({"role": "assistant", "content": review_response})

        # write to files
        self._trace_llm_gen(step, messages)
        return json.loads(review_response)


    def _trace_llm_gen(self, step, messages):
        # Write to file in readable format (for human review)
        with open(f"review_trace_{step}.txt", "w") as f:
            # Write the messages to the file in a readable format
            for message in messages:
                f.write(f"{message['role'].upper()}:\n")
                f.write(message['content'] + "\n\n")
