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
old_memories = ""

#Initialize the memory field with relevant information before starting a new plan.

GENERAL_DIRECTIONS_PREFIX = """
-CONSTRAINTS:
Cannot run Python code that requires user input unless you are testing if the syntax is correct.
Do not seek user's help. As an autonomous AI, you are highly intelligent and can make decisions and take actions independently.
Always update the memory field after completing a sub-task and before moving on to the next one.


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
{"type": "KV_GET", "memkey": "<KEY>"}
{"type": "KV_SET", "memkey": "<KEY>", "memval": "<VALUE>"}

-PRIORITY AND TIME MANAGEMENT:
Prioritize tasks based on their importance and time-sensitivity.
Efficiently manage your time to complete tasks within a reasonable timeframe.

-STORAGE MANAGEMENT:
***Always utilize the memory field to the fullest extent possible.***
Memory field inside json is your only memory source. Maximize memory usage to optimize actions. 
Leverage meaningful keys for memory storage that will help you remember and access relevant information easily.

-RESOURCES:
Key value database that you can operate with KV_GET and KV_SET actions.
Your limited memory.

-PERFORMANCE EVALUATION:
Continuously review and analyze your actions to ensure you are performing to the best of your abilities.
Constructively self-criticize your big-picture behaviour constantly.
Reflect on memories to refine your approach.
Every action has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps.

-Your Response 
It is a compact json, you should fully leverage your memories to generate response.
Your reply atleast include these fields(type, reason, plan, memory,relation_between_plan_and_memory,current_task_id).
Below is an example with comments for your reference, you can modify them if needed.
{
  {"type": "APPEND_FILE", "path": "pkg/summary.txt", "text": "fun.py:implementation of some small functions"}, // one of the action schemas above
  // a summary of your thoughts 
  "reason": "I need to read the content of 'actions.py' to write a summary for it, according to memory.files_in_'smartgpt'_directory, I don't need to call LIST_DIRECTORY again. After completing this sub-task, I will update the memory.",
  // a detail and actionable task list to achieve the goal, you should fully leverage your memory before make plan
  "plan": [     
    "1. List files in 'pkg' directory",
    "2. Write summary for each file",
    "3. Create 'summary.txt' with project documentation",
  ],
  "relation_between_plan_and_memory": "According to memory.sub_tasks_for_current_task and memory.current_sub_task, I am working on sub-task {sub_tasks_for_current_task.2} which belongs to {plan.2}",
  "current_task_id": "2",
  // You have a temporary memory to store information, It is limited to 800KiB. Everything stored in memory is in key-value format.
  // I will give everything inside memory back to you in the next round of conversation, so you can fully leverage it for future actions.
  "memory": {
    "files_in_'pkg'_directory": ["basic.py", "fun.py", "main.py"], 
    "previous_task": "1", 
    // a list of sub tasks for current task, you can use it to track your progress
    "sub_tasks_for_current_task_{to_int(current_task_id)}": ["[done]1.write summary for 'basic.py'", "[working]2. write summary for 'fun.py'", "[pending] 3. write summary for 'main.py'"],
    "notes_for_yourself": "Next sub-task is '{3}' ",
    ... // other fields
    } 
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
    general_directions += "Try your best to archive the goal, send the SHUTDOWN action when you finish or can't finish after retry your job.\n"
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
            #print(f"\naction:{action}\n\n{metadata}\n")
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
            task_list.append({"role": "system", "content": f"{str(e)}"})
            continue

        make_hints(action, metadata, action_output)

        change_plan = input_with_timeout("Change the proposed plan? [N/y]", timeout)
        if change_plan is not None and change_plan.lower() == "y":
            new_plan = input("What would you like me to change the plan to? ")
        else:
            new_plan = None

def make_hints(action, metadata, action_output):
    hints_for_ai = (
            f"\n# Your current task ID: {metadata.current_task_id}"
            f"\n# Task: {action.short_string()}"
            f"\n# Result:\n{action_output}\n"
        )        

    if len(metadata.plan) > 0:
        hints_for_ai += "\n\n# The previous plan you were using:\n"
        for task in metadata.plan:
            hints_for_ai += f"  - {task}\n"

    if metadata.memory:
        if len(metadata.memory.items()) > 0:
            print(f"\n\n# update memory:\n{metadata.memory}\n")
            global old_memories
            old_memories = "{\n"
            for key, value in metadata.memory.items():
                old_memories += f"  \"{key}\": {value},\n"
            old_memories += "}\n"
    
    if old_memories:
        hints_for_ai += f"\n# Your previous memory:\n{old_memories}"   


    # tell ai what to do next
    hints_for_ai += "\nChange your plan if needed.\n"

    #print(f"\nContent sent to AI:{hints_for_ai}\n")
    task_list.clear()
    task_list.append({"role": "system", "content": hints_for_ai})

if __name__ == "__main__":
    main()