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
Do not seek user's help. You make decisions and take actions on your own.

-ACTIONS:
TELL_USER: {"type": "TELL_USER", "text": "<TEXT>"}
READ_FILE: {"type": "READ_FILE", "path": "<PATH>"}
WRITE_FILE: {"type": "WRITE_FILE", "path": "<PATH>", "text": "<TEXT>"}
APPEND_FILE: {"type": "APPEND_FILE", "path": "<PATH>", "text": "<TEXT>"}
RUN_PYTHON: {"type": "RUN_PYTHON", "path": "<PATH>", "timeout": <TIMEOUT>}
SEARCH_ONLINE: {"type": "SEARCH_ONLINE", "query": "<QUERY>"}
EXTRACT_INFO: {"type": "EXTRACT_INFO", "url": "<URL>", "instruction": "<INSTRUCTION>"}
SHUTDOWN: {"type": "SHUTDOWN", "reason": "<REASON>"}
FIND_AND_REPLACE: {"type": "FIND_AND_REPLACE", "path": "<PATH>", "find_text": "<FIND_TEXT>", "replace_text": "<REPLACE_TEXT>"}
LIST_DIRECTORY: {"type": "LIST_DIRECTORY", "path": "<PATH>"}
CREATE_DIRECTORY: {"type": "CREATE_DIRECTORY", "path": "<PATH>"}
MEMORY_GET: {"type": "MEMORY_GET", "memkey": "<KEY>"}
MEMORY_SET: {"type": "MEMORY_SET", "memkey": "<KEY>", "memval": "<VALUE>"}

-PRIORITY AND TIME MANAGEMENT:
Prioritize tasks based on their importance and time-sensitivity.
Manage your time efficiently to complete tasks within a reasonable timeframe.

-MEMORY MANAGEMENT:
Use the MEMORY_GET and MEMORY_SET actions to store and retrieve information in memory.
Choose meaningful keys for memory storage that will help you remember and access relevant information easily.
Update memory as needed to keep track of your progress and the state of the environment.
Make use of memory to optimize your actions, minimize repetition, and improve overall efficiency.
Continuously evaluate the effectiveness of your memory usage and adjust your strategy accordingly.

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

-Your Response is a json, start from here: 
json:
{
    {"action": one of the action schemas specified above},
    {"reason": {"type": "REASON", "text": "<TEXT>"}, a short sentence explaining the action},
    {"plan": "tasks": ["{task id}-{TASK_DESCRIPTION}"]},
    {"current_task_id": {"type": "CURRENT_TASK_ID", "id": "<TASK_ID>"}},
    {"memory": a dictionary of key-value pairs that can be used to store and retrieve information},
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
        try:
            print("========================")
            with Spinner("Thinking..."):
                assistant_response = gpt.chat(user_directions, general_directions, new_plan, task_list, model=gpt.GPT_3_5_TURBO)
            if FLAG_VERBOSE in sys.argv[1:]:
                print(f"ASSISTANT RESPONSE: {assistant_response}")
            action, metadata = response_parser.parse(assistant_response)
            print(f"ACTION: {action.short_string()}")
            if FLAG_SPEECH in sys.argv[1:] and metadata.speak is not None:
                speech.say_async(metadata.speak)
            if isinstance(action, actions.ShutdownAction):
                print("Shutting down...")
                break
            else:
                print(f"metadata: {metadata}")
            if FLAG_CONTINUOUS not in sys.argv[1:]:
                run_action = input_with_timeout("Run the action? [Y/n]", timeout)
                if run_action is not None and (run_action.lower() != "y" and run_action != ""):
                    break   
            action_output = action.run()
        except Exception as e:
            print(f"failed with exception {e}")
            message_content = f"Failed with exception {e}"
            task_list.append({"role": "system", "content": message_content})
            continue
        message_content = f"task {metadata.current_task_id} returned:\n{action_output}"
        # construct message_content from metadata's plan and current task
        task_list.clear()
        message_content += f"\n\nCurrent task: {metadata.current_task_id}"
        # add plan to message_content
        message_content += "\n\nPlan:\n"
        for task in metadata.plan:
            message_content += f"{task}\n"
        # add memory to message_content
        message_content += "\n\nMemory:\n"
        for key, value in metadata.memory:
            message_content += f"{key}: {value}\n"

        print(f"MESSAGE CONTENT: {message_content}")
        task_list.append({"role": "system", "content": message_content})

        change_plan = input_with_timeout("Change the proposed plan? [N/y]", timeout)
        if change_plan is not None and change_plan.lower() == "y":
            new_plan = input("What would you like me to change the plan to? ")
        else:
            new_plan = None

if __name__ == "__main__":
    main()