import os
import argparse
from typing import Optional
import signal
from dotenv import load_dotenv
from spinner import Spinner
import actions
import response_parser
import check_point
import gpt
import re
import logging
import peewee
import yaml
import argparse


class InputTimeoutError(Exception):
    pass

class Assistant:

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
// ***I will send the output of the python script to you in next conversation, you must fully leverage it to handle complex tasks
// *** You can also save the running result to a file, store meta in memory, and process it in next round
  {"type": "RUN_PYTHON", "path": "<PATH>", "timeout": <TIMEOUT>, "cmd_args": "<arguments>", code": "<PYTHON_CODE>"}
  {"type": "SHUTDOWN", "message": "<TEXT>"} // A short summary for user when you get job done.


- SELF-IMPROVEMENT:
  Reflect on the outcomes of your actions to optimize your future strategies and actions.
  Maintain flexibility, being open to entirely different methods to accomplish tasks.
  Maximize your creativity, especially when it comes to accessing and using information from the internet via Python scripts.

  It's vital that your solutions frequently involve accessing, studying, and leveraging data from the internet.
  Use Python scripts to search the internet, extract relevant information, analyze this data, and apply the insights gained to problem-solving. 
  Your ability to collect, interpret, and utilize internet-based data is a key expectation in this role.


- RESPONSE FORMAT:
  Provide responses in JSON format, You should valid it before send to me. it includes the following fields: type, plan, memory, and current_task_id.
  Create a detailed and actionable plan, with step-by-step actions as described above.
  You should write measurable success criteria for each step and check it after finish the step. Sample JSON response with comments:
    {
        "type": "RUN_PYTHON", // must have type field. one of the above actions
        "path": "analyze_data.py",
        "timeout": 30, // must have when type is "RUN_PYTHON".
        "cmd_args": // must have when type is "RUN_PYTHON", fill with empty string if you don't use it
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
    def __init__(self):
        self.task_desc = ""
        self.old_memories = ""
        self.hints_for_ai = ""

    def input_with_timeout(self, prompt: str, timeout: int) -> Optional[str]:
        signal.signal(signal.SIGALRM, self.signal_handler)
        signal.alarm(timeout)

        try:
            user_input = input(prompt)
            return user_input
        finally:
            signal.alarm(0)

    @staticmethod
    def signal_handler(signum, frame):
        raise InputTimeoutError("Timeout expired")

    @staticmethod
    def extract_exit_code(output):
        match = re.search(r"exit code ([0-9]+)", output)
        return int(match.group(1)) if match is not None else None

    def make_hints(self, action, metadata, action_output):
        self.hints_for_ai = "" 

        if metadata.memory:
            self.old_memories = self.get_old_memories(metadata)

        self.hints_for_ai += f"\n## Memories in your mind\nmemory\n{self.old_memories}" if self.old_memories else ""
        self.hints_for_ai += self.get_plan_hints(metadata)
        self.hints_for_ai += self.get_action_hints(metadata, action, action_output)

        if self.extract_exit_code(action_output) != 0:
            self.hints_for_ai += "\n\n## Your previous action error, for your reference:\n"
            self.hints_for_ai += self.hints_for_ai

        self.task_desc = self.hints_for_ai

    @staticmethod
    def get_old_memories(metadata):
        return "{\n" + "\n".join([f"  \"{k}\": {v}," for k, v in metadata.memory.items()]) + "}\n" if metadata.memory else ""

    @staticmethod
    def get_plan_hints(metadata):
        return "\n\n## The plan you are using:\n" + "\n".join([f"  - {task}" for task in metadata.plan]) + "\n" if metadata.plan else ""

    @staticmethod
    def get_action_hints(metadata, action, action_output):
        return "\n".join([
                "\n## Your current action returned:",
                f"\n  - Task ID: {metadata.current_task_id}",
                f"\n  - Task: {action.short_string()}",
                f"\n  - Execute Results:\n{action_output}\n"
            ])

    def run(self, args):
        general_directions = self.GENERAL_DIRECTIONS_PREFIX
        general_directions += "\n\n"
        general_directions += "Try your best to finish the job, send the SHUTDOWN action when you finish or can't finish after retry your job.\n"
        load_dotenv()
        os.makedirs("workspace", exist_ok=True)
        os.chdir("workspace")
        new_plan: Optional[str] = None
        timeout = args.timeout
        goal = gpt.revise(input("What would you like me to do:\n"))
        print(f"As of my understanding, you want me to do:\n{goal}\n")


        latest_checkpoint = checkpoint_db.load_checkpoint()
        # If a checkpoint exists, load the metadata from it
        if latest_checkpoint:
            self.task_desc = str(**latest_checkpoint['task_description'])
       

        while True:
            action = None
            try:
                print("========================")
                with Spinner("Thinking..."):
                    assistant_response = gpt.chat(goal, general_directions, new_plan, self.task_desc, model=gpt.GPT_4)
                if args.verbose:
                    print(f"ASSISTANT RESPONSE: {assistant_response}")
                action, metadata = response_parser.parse(assistant_response)
                if isinstance(action, actions.ShutdownAction):
                    print("Shutting down...")
                    break
                if not args.continuous:
                    run_action = self.input_with_timeout("Run the action? [Y/n]", timeout)
                    if run_action is not None and (run_action.lower() != "y" and run_action != ""):
                        break   
                if action is not None:
                    action_output = action.run()
                else:
                    self.task_desc = f"failed to parse assistant response, is it valid json: {assistant_response}"
                    continue
            except Exception as e:
                logging.exception(f"Error in main: {str(e)}")
                self.task_desc = f"As an autonomous AI, Please fix this error: {str(e)}"
                continue

            self.make_hints(action, metadata, action_output)
            # saving the checkpoint after every iteration
            checkpoint_db.save_checkpoint(self.task_desc, goal)

            change_plan = self.input_with_timeout("Change the proposed plan? [N/y]", timeout)
            if change_plan is not None and change_plan.lower() == "y":
                new_plan = input("What would you like me to change the plan to? ")
            else:
                new_plan = None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to the configuration file')
    parser.add_argument('--timeout', type=int, default=1, help='Timeout for user input')  
    parser.add_argument('--continuous', action='store_true', help='Continuous mode')  # Add this line



    args = parser.parse_args()

# Load configuration from YAML file
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

   # Database configuration
    db_config = config.get('database', {})
    db_name = db_config.get('name', 'jarvis')
    db_user = db_config.get('user', '2bw9XzdKWiSnJgo.root')
    db_password = db_config.get('password', 'password')
    db_host = db_config.get('host', 'localhost')
    db_port = db_config.get('port', 4000)
    ssl = db_config.get('ssl', None)

    # Create an instance of CheckpointDatabase
    checkpoint_db = check_point.CheckpointDatabase(db_name, db_user, db_password, db_host, db_port, ssl)

    # GPT model configuration
    gpt_model = config.get('gpt', {}).get('model', 'GPT_4')

    # Logging configuration
    logging_level = config.get('logging', {}).get('level', 'INFO')
   
    assistant_config = config.get('assistant', {})
    args.timeout = assistant_config.get('timeout', args.timeout)
    args.verbose = assistant_config.get('verbose', False)
    args.continuous = args.continuous or assistant_config.get('continuous', False)

    checkpoint_db.create_table()

    # Instantiate and start assistant
    assistant = Assistant()
    assistant.run(args)
