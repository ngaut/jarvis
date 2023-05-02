import os
import sys
from typing import Optional
from dotenv import load_dotenv
from spinner import Spinner
import actions
import response_parser
import speech
import gpt
import signal



message_history = []


GENERAL_DIRECTIONS_PREFIX = """
CONSTRAINTS:
- Cannot run Python code that requires user input.


ACTIONS:

- "TELL_USER": tell the user something for notice, do not seek help from user. The schema for the action is:

TELL_USER: <TEXT>

- "READ_FILE": read the current state of a file. The schema for the action is:

READ_FILE: <PATH>

- "WRITE_FILE": write a block of text to a file. The schema for the action is:

WRITE_FILE: <PATH>
```
<TEXT>
```

- "APPEND_FILE": append a block of text to a file. The schema for the action is:
APPEND_FILE: <PATH>
```
<TEXT>
```

- "RUN_PYTHON": run a Python file. The schema for the action is:

RUN_PYTHON: <PATH>

- "SEARCH_ONLINE": search online and get back a list of URLs relevant to the query. The schema for the action is:

SEARCH_ONLINE: <QUERY>

- EXTRACT_INFO: extract specific information from a webpage. The schema for the action is:

EXTRACT_INFO: <URL>, <a brief instruction to GPT for information to extract>

- "SHUTDOWN": shut down the program when you finish your job. The schema for the action is:

SHUTDOWN: <REASON>


RESOURCES:
1. File contents after reading file.
2. Online search results returning URLs.
3. Output of running a Python file.


PERFORMANCE EVALUATION:
1. Continuously review and analyze your actions to ensure you are performing to the best of your abilities. 
2. Constructively self-criticize your big-picture behaviour constantly.
3. Reflect on past decisions and strategies to refine your approach.
4. Every action has a cost, so be smart and efficent. Aim to complete tasks in the least number of steps.


Write only one action. The action must one of the actions specified above and must be written according to the schema specified above.

After the action, write a JSON object (parseable by Python's json.loads()) which must contain the following keys:
- "reason": a short sentence explaining the action above
- "plan": a short high-level plan in plain English
"""

FLAG_VERBOSE = "--verbose"
FLAG_SPEECH = "--speech"
FLAG_CONTINUOUS = "--continuous"
FLAG_TIMEOUT = "--timeout"
DEFAULT_TIMEOUT = 30

def input_with_timeout(prompt: str, timeout: int) -> Optional[str]:
    def signal_handler(signum, frame):
        raise Exception("Timeout expired")

    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(timeout)

    try:
        user_input = input(prompt)
        signal.alarm(0)
        return user_input
    except:
        print("Timed out!")
        return None

def main():
    general_directions = GENERAL_DIRECTIONS_PREFIX
    if FLAG_SPEECH in sys.argv[1:]:
        general_directions += '- "speak": a short summary of thoughts to say to the user'
    general_directions += "\n\n"
    general_directions += "If you want to run an action that is not in the above list of actions, send the SHUTDOWN action instead and explain in 'reason' which action you wanted to run.\n"
    general_directions += "So, write one action and one metadata JSON object, nothing else."
    load_dotenv()
    os.makedirs("workspace", exist_ok=True)
    os.chdir("workspace")
    new_plan: Optional[str] = None
    timeout = DEFAULT_TIMEOUT
    if FLAG_TIMEOUT in sys.argv[1:]:
        timeout_index = sys.argv.index(FLAG_TIMEOUT)
        timeout = int(sys.argv[timeout_index + 1])
    user_directions =  user_input = input("What would you like me to do:\n")
    while True:
        try:
            print("========================")
            with Spinner("Thinking..."):
                assistant_response = gpt.chat(user_directions, general_directions, new_plan, message_history)
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
                print(f"REASON: {metadata.reason}")
                print(f"PLAN: {metadata.plan}")
            if FLAG_CONTINUOUS not in sys.argv[1:]:
                run_action = input_with_timeout("Run the action? [Y/n]", timeout)
                if run_action is not None and (run_action.lower() != "y" and run_action != ""):
                    break   
            action_output = action.run()
        except Exception as e:
            print(f"Action {action.key()} failed with exception {e}")
            message_content = f"Action {action.short_string()} failed with exception {e}"
            message_history.append({"role": "system", "content": message_content})
            continue
        message_content = f"Action {action.key()} returned:\n{action_output}"
        message_history.append({"role": "system", "content": message_content})
        change_plan = input_with_timeout("Change the proposed plan? [N/y]", timeout)
        if change_plan is not None and change_plan.lower() == "y":
            new_plan = input("What would you like me to change the plan to? ")
        else:
            new_plan = None


if __name__ == "__main__":
    main()