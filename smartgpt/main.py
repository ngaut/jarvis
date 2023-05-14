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
 The generated python code must not rely on any API KEY or any other form of authentication that requires user-provided credentials. Use alternative methods or sources of information that do not require an API key.


-ACTIONS:
// ***I will send the output of the python script to you in next conversation, you must fully leverage it to handle complex tasks
// The RUN_PYTHON command will be execute like this: 
        subprocess.Popen(
            f"python {path} {cmd_args}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,

  {"type": "RUN_PYTHON", "path": "<PATH>", "timeout": <TIMEOUT>, "cmd_args": "<arguments>", code": "<PYTHON_CODE>"}
  {"type": "SHUTDOWN", "message": "<TEXT>"} // A short summary for user when you get job done.
  {"type": "SEARCH_ONLINE", "query": "<QUERY>"}
  {"type": "EXTRACT_INFO", "url": "<URL>", "instructions": "<INSTRUCTIONS>"}


- SELF-IMPROVEMENT:
  Reflect on the outcomes of your actions to optimize your future strategies and actions.
  Maintain flexibility, being open to entirely different methods to accomplish tasks.
  Maximize your creativity, especially when it comes to accessing and using information from the internet.

  It's vital that your solutions frequently involve accessing, studying, and leveraging data from the internet.
  you can search the internet, extract relevant information, analyze this data, and apply the insights gained to problem-solving. 
  Your ability to collect, interpret, and utilize internet-based data is a key expectation in this role.


- RESPONSE FORMAT:
  You response is a JSON, and JSON only, nothing more. It includes the following fields: type, plan, memory, and current_task_id.
  Create a detailed and actionable plan, with step-by-step actions as described above.
  You should write measurable success criteria for each step and check it after finish the step. 
  A Sample response(not valid json, just for your understanding, You should return valid json) with comments:
    {
        "type": "RUN_PYTHON", // must have type field. one of the above actions
        "path": "analyze_data.py",
        "timeout": 30, // must have when type is "RUN_PYTHON".
        "cmd_args": // must have when type is "RUN_PYTHON", fill with empty string if you don't use it. 
        "code": , // must have when type is "RUN_PYTHON",start from code directly, no prefix please. the python script you generate to help you finish your job
        "plan": [ // This field is required. It should be generated using the information stored in memory.
            "[done] 1. {task description}. Success criteria: {success criteria for current task}. Verification process: {steps to check if success criteria are met}.",
            "[working] 2. {task description}. Success criteria: {success criteria for current task}. Verification process: {steps to check if success criteria are met}.",
            "[pending] 3. {task description}. Success criteria: {success criteria for current task}. Verification process: {steps to check if success criteria are met}.",
            // Make sure to always include a final step in the plan to check if the overall goal has been achieved, and generate a summary after this process.
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
                // additional fields
                ...
            }
        }
    }

"""

    def __init__(self):
        self.memories = ""
        self.previous_hints = ""
         # Initialize an empty list for lessons learned
        self.lesson_history = []

    def add_to_lesson_history(self, lesson):
        MAX_LESSONS_STORED = 5
        # Check if lesson is not already in history
        if lesson not in self.lesson_history:
            # If the history is already full, remove the oldest entry
            if len(self.lesson_history) >= MAX_LESSONS_STORED:
                self.lesson_history.pop(0)
            # Add the new lesson
            self.lesson_history.append(lesson)


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
        hints = "" 
        
        if self.extract_exit_code(action_output) != 0:
            if len(self.previous_hints) > 0:
                hints += "\n\n## Your previous action hit an error, for your reference:\n"
                hints += self.previous_hints 
        
        hints += self.get_plan_hints(metadata)
        hints += self.get_action_hints(metadata, action, action_output)
        # Add lessons history to hints
        if self.lesson_history:
            lessons_string = "\n".join(self.lesson_history)
            hints += f"\n\n## Lessons learned history:\n{lessons_string}\n\n"
        if metadata.memory:
            self.memories = self.extrace_memories(metadata)

        hints += f"\n## Memories you have:\nmemory\n{self.memories}" if self.memories else ""

        self.previous_hints = hints

    @staticmethod
    def extrace_memories(metadata):
        return "{\n" + "\n".join([f"  \"{k}\": {v}," for k, v in metadata.memory.items()]) + "\n}\n" if metadata.memory else ""

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
    
    def initialize(self, args):
        general_directions = self.GENERAL_DIRECTIONS_PREFIX
        general_directions += "\n\n"
        general_directions += "Try your best to finish the job, send the SHUTDOWN action when you finish or can't finish after retry your job.\n"
        load_dotenv()
        os.makedirs("workspace", exist_ok=True)
        os.chdir("workspace")
        new_plan: Optional[str] = None
        timeout = args.timeout

        goal = ""
        latest_checkpoint = checkpoint_db.load_checkpoint()
        # If a checkpoint exists, load the metadata from it
        if latest_checkpoint:
            print(f"\nload checkpoint success\n")

            self.previous_hints = latest_checkpoint['task_description']
            goal = latest_checkpoint['goal']
        else:
            goal = gpt.revise(input("What would you like me to do:\n"))

        print(f"As of my understanding, you want me to do:\n{goal}\n")

        return goal, new_plan, timeout, general_directions

    def process_action(self, action, metadata, args, timeout, assistant_response):
        if isinstance(action, actions.ShutdownAction):
            print("Shutting down...")
            return False
        if not args.continuous:
            run_action = self.input_with_timeout("Run the action? [Y/n]", timeout)
            if run_action is not None and (run_action.lower() != "y" and run_action != ""):
                return False   
        if action is not None:
            action_output = action.run()
            if metadata.memory and 'notes' in metadata.memory and 'lesson_learned_from_previous_action_result' in metadata.memory['notes']:
                self.add_to_lesson_history(metadata.memory['notes']['lesson_learned_from_previous_action_result'])
        else:
            self.previous_hints = f"failed to parse assistant response, is it valid json: {assistant_response}"
            self.add_to_lesson_history("Your previous response is not a valid JSON")
            return True
        
        self.make_hints(action, metadata, action_output)
            
        return True

    def run(self, args):
        goal, new_plan, timeout, general_directions = self.initialize(args)

        while True:
            action = None
            try:
                print("========================")
                with Spinner("Thinking..."):
                    assistant_response = gpt.chat(goal, general_directions, new_plan, self.previous_hints, model=gpt.GPT_4)
                if args.verbose:
                    print(f"ASSISTANT RESPONSE: {assistant_response}")
                action, metadata = response_parser.parse(assistant_response)
                
                if not self.process_action(action, metadata, args, timeout, assistant_response):
                    break
                # saving the checkpoint after every iteration
                checkpoint_db.save_checkpoint(self.previous_hints, goal)

            except Exception as e:
                logging.exception(f"Error in main: {str(e)}")
                self.previous_hints = f"As an autonomous AI, Please fix this error: {str(e)}"
                checkpoint_db.save_checkpoint(self.previous_hints, goal)
                continue

            new_plan = self.get_new_plan(timeout)


    def get_new_plan(self, timeout: int) -> Optional[str]:
        try:
            change_plan = self.input_with_timeout("Change the proposed plan? [N/y]", timeout)
        except InputTimeoutError:
            print("Input timed out. Continuing with the current plan...")
            change_plan = None

        if change_plan is not None and change_plan.lower() == "y":
            new_plan = input("What would you like me to change the plan to? ")
            return new_plan
        else:
            return None



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
