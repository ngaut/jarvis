from typing import Dict, List

from jarvis.smartgpt import gpt
from jarvis.smartgpt import preprompts


def clarify(goal: str, model: str) -> List[Dict[str, str]]:
    messages = [{"role": "system", "content": preprompts.get("clarify_sys")}]
    user_input = f"The goal:\n{goal}\n"

    while True:
        print()
        messages = gpt.chat(model, messages, user_input)
        if messages[-1]["content"].strip() == "Nothing more to clarify.":
            break
        if messages[-1]["content"].strip().lower().startswith("no"):
            print("Nothing more to clarify.")
            break

        print(messages[-1]["content"])
        user_input = input('\n(answer in text, or "c" to move on)\n')

        if not user_input or user_input == "c":
            print()
            print("\n(letting Jarvis make its own assumptions)\n")
            messages = gpt.chat(
                model,
                messages,
                "Make your own assumptions and state them explicitly before starting",
            )
            return messages

        user_input += preprompts.get("clarify_user")

    return messages


def clarify_and_summarize(goal: str, model: str) -> str:
    # Interactively clarify user goals
    messages = clarify(goal, model)

    # Summarize the messages to a clear goal
    messages = [{"role": "system", "content": "You are an AI assistant to clarify user's goal"}] + messages[1:]

    user_prompt = "Summary the goal into a single sentence to make it clear and detailed"
    resp = gpt.complete_with_messages(model, messages, user_prompt)
    return resp
