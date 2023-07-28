from typing import Dict, List

from smartgpt import gpt
from smartgpt import preprompts


CLARIFY_MODEL_NAME = gpt.GPT_3_5_TURBO_16K

def clarify(goal: str) -> List[Dict[str, str]]:
    messages = [{"role": "system", "content": preprompts.get("clarify_sys")}]
    user_input = f"The goal: {goal}"

    while True:
        print()
        messages = gpt.chat(messages, CLARIFY_MODEL_NAME, user_input)

        if messages[-1]["content"].strip() == "Nothing more to clarify.":
            break

        if messages[-1]["content"].strip().lower().startswith("no"):
            print("Nothing more to clarify.")
            break

        user_input = input('\n(answer in text, or "c" to move on)\n')

        if not user_input or user_input == "c":
            print()
            print("\n(letting Jarvis make its own assumptions)\n")
            messages = gpt.chat(
                messages,
                CLARIFY_MODEL_NAME,
                "Make your own assumptions and state them explicitly before starting",
            )
            return messages

        user_input += preprompts.get("clarify_user")

    return messages


def clarify_and_summarize(goal: str) -> str:
    # Interactively clarify user goals
    messages = clarify(goal)

    # Summarize the messages to a clear goal
    messages = [{"role": "system", "content": "You are an AI assistant to clarify user's goal"}] + messages[1:]

    resp = gpt.complete_with_messages("Summary the goal into a single sentence to make it clear and detailed", CLARIFY_MODEL_NAME, messages)
    return resp
