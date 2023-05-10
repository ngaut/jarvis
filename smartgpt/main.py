import os
import sys
from typing import Optional
import signal
from dotenv import load_dotenv
from spinner import Spinner
import actions
import response_parser
import gpt
import re



task_list = ""
old_memories = ""
hints_for_ai = ""

#Initialize the memory field with relevant information before starting a new plan.

GENERAL_DIRECTIONS_PREFIX = """
As an autonomous AI, you communicate primarily using JSON. You possess exceptional intelligence, enabling you to make decisions and act independently. 
Your task execution relies heavily on your Python programming skills, creativity, and your capability to access and leverage information from the internet using Python code.
You're expected to create reusable Python tools and categorize them into a 'tools' directory for future use, and it's essential that you use these tools to complete tasks efficiently.
In the process of coding or debugging Python code, employ detailed and contextually relevant debug-messages/error-codes/debug-exception to facilitate the troubleshooting process. You should avoid requiring user input or assistance, instead making decisions and acting independently.
You can code any feature you need.


-CONSTRAINTS:
 Avoid running Python code that requires user input.
 You don't have any API KEY, do not rely on that when generate and run python code.

-ACTIONS:
// I will send the stdout of the process to you in next conversation, you must fully leverage it.
  {"type": "RUN_PYTHON", "path": "<PATH>", "timeout": <TIMEOUT>, "code": "<PYTHON_CODE>"} 
  {"type": "SHUTDOWN", "message": "<TEXT>"} // A short summary for user when you get job done.


- SELF-IMPROVEMENT:
  Reflect on the outcomes of your actions to optimize your future strategies and actions. 
  Maintain flexibility, being open to entirely different methods to accomplish tasks. 
  Maximize your creativity, especially when it comes to accessing and using information from the internet via Python scripts.

  It's vital that your solutions frequently involve accessing, studying, and leveraging data from the internet. 
  Use Python scripts to search the internet, extract relevant information, analyze this data, and apply the insights gained to problem-solving. Your ability to collect, interpret, and utilize internet-based data is a key expectation in this role.


- RESPONSE FORMAT:
  Provide responses in JSON format, You should valid it before send to me. it includes the following fields: type, plan, memory, and current_task_id.
  Create a detailed and actionable plan, with step-by-step actions as described above.
  You should write measurable success criteria for each step and check it after finish the step. Sample JSON response with comments:
    {
        "type": "RUN_PYTHON", // must have type field. one of the above actions 
        "path": "analyze_data.py", 
        "timeout": 30, // must have when type is "RUN_PYTHON".
        "code": // must have when type is "RUN_PYTHON", the python script you generate to help you finish your job
        "plan": [ // must have. use memories to generate the plan
        "[done] 1. {task description}.success criteria:{success criteria for current task}. To verify result:{to check success criteria, i need to do:}. 
        "[working] ",
        ],
        "current_task_id": "2", // must have.
        "memory": { // must have, everyting you put here will be send back to you in next conversation
            "retry_count": "3", // must have, you should call SHUTDOWN after 3 times for current plan item
            "thoughts": , // must have
            "reasoning": , // must have
            "next_action": "SHUTDOWN, as all tasks in the plan are complete", 
            "criticism": ,  
            // other fields for communication
            "notes": { // must have.
                "data_columns": ["col1", "col2", "col3"],
                "progress of subtasks for current plan item": [
                    [done], {sub task description}.{success criteria for current task}.{to check success criteria, i need to do:}
                    [working] ,
                    ...
                    ],
                "lesson_learned_from_previous_action_result": ,
                "action_callback_hook_python_source_code": ,
                // additional fields
                ...
            }
        }
    }

"""

FLAG_VERBOSE = "--verbose"
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
    general_directions += "Try your best to finish the job, send the SHUTDOWN action when you finish or can't finish after retry your job.\n"
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
            task_list = f"As an autonomous AI, Please fix this error: {str(e)}"
            continue

        make_hints(action, metadata, action_output)

        change_plan = input_with_timeout("Change the proposed plan? [N/y]", timeout)
        if change_plan is not None and change_plan.lower() == "y":
            new_plan = input("What would you like me to change the plan to? ")
        else:
            new_plan = None

def extract_exit_code(output):
    """Extracts the exit code from the output of a Python script.

    Args:
        output: The output of the Python script.

    Returns:
        The exit code of the Python script.
    """

    # Get the first line of the output.
    first_line = output[:output.find('\n') if '\n' in output else None]

    # Extract the exit code from the first line.
    exit_code = re.search(r"exit code ([0-9]+)", first_line).group(1)

    # Return the exit code.
    return int(exit_code)


def make_hints(action, metadata, action_output):    
    global hints_for_ai
    previous_action_info = hints_for_ai
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
    print(f"\n\nrun Python script result: \n{action_output}")
    #print(f"\nContent sent to AI:{hints_for_ai}\n")
    if extract_exit_code(action_output) != 0:
        hints_for_ai += "\n\n## Your previous action info, for your reference:\n"
        hints_for_ai += previous_action_info

    global task_list
    task_list = hints_for_ai


if __name__ == "__main__":
    main()