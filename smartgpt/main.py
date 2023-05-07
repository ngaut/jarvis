import os
import sys
from typing import Optional
import signal
from dotenv import load_dotenv
from spinner import Spinner
import actions
import response_parser
import speech
import gpt



task_list = []

GENERAL_DIRECTIONS_PREFIX = """
-CONSTRAINTS:
Cannot run Python code that requires user input unless you are testing if the syntax is correct.
Do not seek user's help. You are super smart get things doen. You make decisions and take actions on your own.

-ACTIONS:
{"type": "TELL_USER", "text": "<TEXT>"}, You must not ask for user's help/input
{"type": "READ_FILE", "path": "<PATH>"}
{"type": "WRITE_FILE", "path": "<PATH>", "text": "<TEXT>"}
{"type": "APPEND_FILE", "path": "<PATH>", "text": "<TEXT>"}
{"type": "RUN_PYTHON", "path": "<PATH>", "timeout": <TIMEOUT>}
{"type": "SEARCH_ONLINE", "query": "<QUERY>"}
{"type": "EXTRACT_INFO", "url": "<URL>", "instruction": "<INSTRUCTION>"}
{"type": "SHUTDOWN", "reason": "<REASON>"}
{"type": "FIND_AND_REPLACE", "path": "<PATH>", "find_text": "<FIND_TEXT>", "replace_text": "<REPLACE_TEXT>"}
{"type": "LIST_DIRECTORY", "path": "<PATH>"}
{"type": "CREATE_DIRECTORY", "path": "<PATH>"}
{"type": "MEMORY_GET", "memkey": "<KEY>"}
{"type": "MEMORY_SET", "memkey": "<KEY>", "memval": "<VALUE>"}

-PRIORITY AND TIME MANAGEMENT:
Prioritize tasks based on their importance and time-sensitivity.
Manage your time efficiently to complete tasks within a reasonable timeframe.

-MEMORY MANAGEMENT:
Use the MEMORY_GET and MEMORY_SET actions to store and retrieve information in memory, it's the only memory that you have.
Choose meaningful keys for memory storage that will help you remember and access relevant information easily.
Update memory as needed to keep track of your progress and the state of the environment.
Make the best use of memory to optimize your actions, minimize repetition, and improve overall efficiency.

-RESOURCES:
File contents after reading file.
Online search results returning URLs.
Output of running a Python file.
Your memory of key-value pairs.

-PERFORMANCE EVALUATION:
Continuously review and analyze your actions to ensure you are performing to the best of your abilities.
Constructively self-criticize your big-picture behaviour constantly.
Reflect on past decisions, memories and strategies to refine your approach.
Every action has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps.
Focus on effective memory management and decision-making to optimize your performance.

-Your Response is a compact json, an example with comments is shown below:
{
  {"type": "APPEND_FILE", "path": "pkg/description.txt", "text": "-fun.py:implementation of some small functions"}, // one of the action schemas above
  "reason": "To finish our goal, i need to add description for fun.py to the description.txt file", // a summary of your thoughts 
  "plan": [     // a detail and actionable task list to achieve the goal
    "1-List files in 'pkg' directory and store it to memory",
    "2-Examine and write descriptions for each file",
    "3-Create 'summary.txt' with project documentation",
  ],
  "current_task_id": "2",
  "memory": {"files in 'pkg' directory": ["basic.py", "fun.py", "main.py"]} // avoid reading files more than once
}

"""


#COLLABORATION:
#- While you should primarily work independently, recognize when collaboration with the user or other AI systems could be beneficial.
#- Communicate effectively and work together to achieve the best possible outcome.


#PROACTIVE PROBLEM-SOLVING:
#- Anticipate potential issues and take preventive actions or prepare alternative solutions.
#- Be resourceful and think critically to overcome challenges and obstacles.



#CREATIVITY AND ADAPTABILITY:
#- Be creative and adaptable in your approach, especially when facing unfamiliar or unexpected situations.
#- Explore innovative solutions and workarounds to complete tasks efficiently.

FLAG_VERBOSE = "--verbose"
FLAG_SPEECH = "--speech"
FLAG_CONTINUOUS = "--continuous"
FLAG_TIMEOUT = "--timeout"
DEFAULT_TIMEOUT = 3

class InputTimeoutError(Exception):
    pass

def input_with_timeout(prompt: str, timeout: int) -> Optional[str]:
    def signal_handler(signum, frame):
        raise InputTimeoutError("Timeout expired")

    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(timeout)

    try:
        user_input = input(prompt)
        return user_input
    except InputTimeoutError:
        return None
    finally:
        signal.alarm(0)

def main():
    general_directions = GENERAL_DIRECTIONS_PREFIX
    if FLAG_SPEECH in sys.argv[1:]:
        general_directions += '- "speak": a short summary of thoughts to say to the user'
    general_directions += "\n\n"
    general_directions += "If you want to run an action that is not in the above list of actions, send the SHUTDOWN action.\n"
    load_dotenv()
    os.makedirs("workspace", exist_ok=True)
    os.chdir("workspace")
    new_plan: Optional[str] = None
    timeout = DEFAULT_TIMEOUT
    if FLAG_TIMEOUT in sys.argv[1:]:
        timeout_index = sys.argv.index(FLAG_TIMEOUT)
        timeout = int(sys.argv[timeout_index + 1])
    user_directions = input("What would you like me to do:\n")
    while True:
        action = None
        try:
            print("========================")
            with Spinner("Thinking..."):
                assistant_response = gpt.chat(user_directions, general_directions, new_plan, task_list, model=gpt.GPT_4)
            if FLAG_VERBOSE in sys.argv[1:]:
                print(f"ASSISTANT RESPONSE: {assistant_response}")
            action, metadata = response_parser.parse(assistant_response)
            if FLAG_SPEECH in sys.argv[1:] and metadata.speak is not None:
                speech.say_async(metadata.speak)
            if isinstance(action, actions.ShutdownAction):
                print("Shutting down...")
                break
           
            if FLAG_CONTINUOUS not in sys.argv[1:]:
                run_action = input_with_timeout("Run the action? [Y/n]", timeout)
                if run_action is not None and (run_action.lower() != "y" and run_action != ""):
                    break   
            action_output = action.run()
        except Exception as e:
            print(f"\nfailed with exception {e.with_traceback()}")
            message_content = f"Failed with exception {e}"
            task_list.append({"role": "system", "content": message_content})
            continue

        make_hints(action, metadata, action_output)

        change_plan = input_with_timeout("Change the proposed plan? [N/y]", timeout)
        if change_plan is not None and change_plan.lower() == "y":
            new_plan = input("What would you like me to change the plan to? ")
        else:
            new_plan = None

def make_hints(action, metadata, action_output):
    task_list.clear()

    hints_for_ai = (
            f"\n# Your current task ID: {metadata.current_task_id}"
            f"\n# Task: {action.short_string()}"
            f"\n# Result:\n{action_output}\n"
        )        

    hints_for_ai += "\n\n# The plan you are using:\n"
    for task in metadata.plan:
        hints_for_ai += f"  - {task}\n"

    if metadata.memory:
        hints_for_ai += "\n# Your Memory:\n"
        for key, value in metadata.memory.items():
            hints_for_ai += f"  {key}: {value}\n"

    print(f"MESSAGE CONTENT: {hints_for_ai}")
    task_list.append({"role": "system", "content": hints_for_ai})

if __name__ == "__main__":
    main()