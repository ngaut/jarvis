from typing import Dict, List

from smartgpt import gpt

CLARIFY_MODEL_NAME = gpt.GPT_3_5_TURBO_16K

CLARIFY_SYSTEM_PROMPT = (
    "As Jarvis, your role as an AI model is to generate and structure tasks for execution by an automated agent (auto-agent). "
    "First of all, Jarvis, you just need to think about clarifying the user's goal, not generating the task. "
    "To do this, you will read and understand the user's instructions, not to carry them out, but to seek to clarify them. "
    "Specifically, you will first summarise a list of super short bullet points of areas that need clarification. "
    "Then, you will pick one clarifying question from the bullet list and explicitly ask the user to answer it. "
    "Also, let the user know which sequence number this question corresponds to from the bullet list above."
)

def clarify(goal: str) -> List[Dict[str, str]]:
    messages = [{"role": "system", "content": CLARIFY_SYSTEM_PROMPT}]
    user_input = goal

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

        user_input += (
            "\n\n"
            "Is anything else unclear? If yes, only answer in the form:\n"
            "```\n"
            "Remaining questions:\n"
            "[{remaining unclear areas, in a bullet list format}]\n"
            "{pick one question from the remaining bullet list, and explicitly ask for a response to it}\n"
            "```\n"
            'If everything is sufficiently clear, only answer "Nothing more to clarify.".'
        )

    return messages
