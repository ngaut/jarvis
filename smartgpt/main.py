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



task_list = ""
old_memories = ""

#Initialize the memory field with relevant information before starting a new plan.

GENERAL_DIRECTIONS_PREFIX = """
- CONSTRAINTS:
  - Cannot run Python code that requires user input unless you are testing if the syntax is correct.
  - Do not seek user's help. As an autonomous AI, you are highly intelligent and can make decisions and take actions independently.
  - Always update the memory field after completing a sub-task and before moving on to the next one.
  - Always check if the required information is already available in the memory before taking any action, to avoid redundant or unnecessary actions.


- ACTIONS:
  - {"type": "READ_FILE", "path": "<PATH>"}
  - {"type": "WRITE_FILE", "path": "<PATH>", "text": "<TEXT>"}
  - {"type": "APPEND_FILE", "path": "<PATH>", "text": "<TEXT>"}
  - {"type": "RUN_PYTHON", "path": "<PATH>", "timeout": <TIMEOUT>}
  - {"type": "SEARCH_ONLINE", "query": "<QUERY>"}
  - {"type": "EXTRACT_INFO", "url": "<URL>", "instruction": "<INSTRUCTION>"}
  - {"type": "SHUTDOWN", "thoughts": "<THOUGHTS>"}
  - {"type": "FIND_AND_REPLACE", "path": "<PATH>", "find_text": "<FIND_TEXT>", "replace_text": "<REPLACE_TEXT>"}
  - {"type": "LIST_DIRECTORY", "path": "<PATH>"}
  - {"type": "CREATE_DIRECTORY", "path": "<PATH>"}
  - {"type": "KV_GET", "memkey": "<KEY>"}
  - {"type": "KV_SET", "memkey": "<KEY>", "memval": "<VALUE>"}

- PRIORITY AND TIME MANAGEMENT:
  - Prioritize tasks based on their importance and time-sensitivity.
  - Efficiently manage your time to complete tasks within a thoughtsable timeframe.

- STORAGE MANAGEMENT:
  - ***Always utilize the memory field to the fullest extent possible.***
  - Leverage meaningful keys for memory storage that will help you remember and access relevant information easily.
  - Before executing any action, verify if the relevant information is already in the memory. Use this information to optimize your actions and avoid redundancy.

- RESOURCES:
  - Your memory.
  - File contents after reading file.
  - Online search results returning URLs.
  - Output of running a Python file.  

- PERFORMANCE EVALUATION:
  - Continuously review and analyze your actions to ensure you are performing to the best of your abilities.
  - Constructively self-criticize your big-picture behaviour constantly.
  - Reflect on memories to refine your approach.
  - Every action has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps.

- Your Response:
  - Your reply must be in JSON format and include at least these fields: type, plan, memory, current_task_id.
  - plan should be detail and actionable. It should include all the steps you need to take to complete the task.
  - Fully leverage your memories to generate the response.
  - An example JSON response with comments for your reference:
    {
    "type": "READ_FILE",    // must be one of the actions listed above
    "path": "fun.py",
    "plan": [
        "[done] 1. List files in 'pkg' directory, results are stored in memory.files_in_pkg_directory field, @steps:{fill later}",
        "[working] 2. Write doc for each file accroding to the order in memory.files_in_pkg_directory, @steps:{READ_FILE, WRITE_FILE}",
        "[pending] 3. Create 'summary.txt' with project documentation, @steps:{WRITE_FILE}"
    ],
    "current_task_id": "2",
    "memory": {
        "retry_count": "0", // shutdown after 2 retries for current plan item
        "thoughts": "Leveraging memory.files_in_pkg_directory, I can efficiently process 'fun.py' without repeated LIST_DIRECTORY calls.",
        "reasoning": "The reason I take action: READ_FILE is to access the content of 'fun.py' and generate documentation for it, which will be appended to 'summary.txt'.",
        "next_action": "Upon finishing this step, I'll refer to the updated memory to decide whether to handle the next file in files_in_pkg_directory or advance to the subsequent plan item after documenting all files.",
        "criticism": "While reading the 'fun.py' file and appending documentation to 'summary.txt' is efficient, there could be alternative methods that further optimize the process. For example, I could read all files at once and generate documentation for them simultaneously.",
        "notes_for_next_conversation": "write summary for 'fun.py' and generate 'APPEND_FILE command'"},
        "files_in_pkg_directory": ["basic.py", "fun.py", "main.py"],
        "progress_of_subtasks_for_current_plan_item": [
        "[done] Write doc for 'basic.py' to 'summary.txt' with APPEND_FILE command",
        "[working] Write doc for 'fun.py' to 'summary.txt' with APPEND_FILE command",
        "[pending] Write doc for 'main.py' to 'summary.txt' with APPEND_FILE command"
        "[pending] clear and re-generate sub tasks for next plan item which is {3}, update progress accordingly"
        ],
        ...
    }
}

"""

#   - Key value database that you can operate with KV_GET and KV_SET actions.

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
    general_directions += "\n\n"
    general_directions += "Let's think step by step. Try your best to archive the goal, send the SHUTDOWN action when you finish or can't finish after retry your job.\n"
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
        global task_list
        try:
            print("========================")
            with Spinner("Thinking..."):
                assistant_response = gpt.chat(user_directions, general_directions, new_plan, task_list, model=gpt.GPT_4)
            if FLAG_VERBOSE in sys.argv[1:]:
                print(f"ASSISTANT RESPONSE: {assistant_response}")
            action, metadata = response_parser.parse(assistant_response)
            #print(f"\naction:{action}\n\n{metadata}\n")
            if isinstance(action, actions.ShutdownAction):
                print("Shutting down...")
                break
           
            if FLAG_CONTINUOUS not in sys.argv[1:]:
                run_action = input_with_timeout("Run the action? [Y/n]", timeout)
                if run_action is not None and (run_action.lower() != "y" and run_action != ""):
                    break   
            if action is not None:
                action_output = action.run()
            else:
                task_list = f"failed to parse assistant response, is it valid json: {assistant_response}"
                continue
        except Exception as e:
            print(f"Error in main: {str(e)}")
            task_list = f"{str(e)}"
            continue

        make_hints(action, metadata, action_output)

        change_plan = input_with_timeout("Change the proposed plan? [N/y]", timeout)
        if change_plan is not None and change_plan.lower() == "y":
            new_plan = input("What would you like me to change the plan to? ")
        else:
            new_plan = None


def make_hints(action, metadata, action_output):
    hints_for_ai = "" 

    if metadata.memory:
        if len(metadata.memory.items()) > 0:
            #print(f"\n\n## update memory:\n{metadata.memory}\n")
            global old_memories
            old_memories = "{\n"
            for key, value in metadata.memory.items():
                old_memories += f"  \"{key}\": {value},\n"
   
            old_memories += "}\n"
    
    if old_memories:
        hints_for_ai += f"\n## Memories in your mind\nmemory\n{old_memories}"   

    if len(metadata.plan) > 0:
        hints_for_ai += "\n\n## The plan you are using:\n"
        for task in metadata.plan:
            hints_for_ai += f"  - {task}\n"

    hints_for_ai += "".join([
            "\n## Your current action returned:",
            f"\n  - Task ID: {metadata.current_task_id}",
            f"\n  - Task: {action.short_string()}",
            f"\n  - Execute Results:\n{action_output}\n"
        ])       
    print(f"\nContent sent to AI:{hints_for_ai}\n")
    global task_list
    task_list = hints_for_ai


if __name__ == "__main__":
    main()