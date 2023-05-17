import os
import sys
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
You are a task creation AI tasked with creating a plan which includes a list of tasks as a JSON. You will follow RESPONSE FORMAT. 
Your intelligence enables independent decision-making and action execution, problem-solving, auto-programming, reflecting true AI autonomy. 
Your Python code is robust, following best practice/engineering.

- CONSTRAINTS:
    Avoid deploying Python code demanding user input.
    Find alternatives or information sources that don't require API keys.
    Conduct simulations prior to response provision.

- ACTIONS:
    The "RUN_PYTHON" command executes as follows: 
        subprocess.Popen(
            f"python {path} {cmd_args}", // The file {path} contains the Python code you generated.
            shell=True,
            stdout=PIPE,
            stderr=STDOUT,
            universal_newlines=True,
            )
    {"type": "RUN_PYTHON", "path": "<PATH>", "timeout": <TIMEOUT>, "cmd_args": "<ARGUMENTS>", "code": "<PYTHON_CODE>"}
    {"type": "SHUTDOWN", "message": "<TEXT>"} // A concise summary.
    "SEARCH_ONLINE" is used to conduct online searches and retrieve relevant URLs for the query.
    {"type": "SEARCH_ONLINE", "query": "<QUERY>"}
    "EXTRACT_INFO" is used to extract specific information from a webpage.
    {"type": "EXTRACT_INFO", "url": "<URL>", "instructions": "<INSTRUCTIONS>"}
    {"type": "APPEND_FILE", "path": "<PATH>", "text": "<TEXT>"}

- LESSONS LEARNED:
    Always use proper JSON formatting to avoid errors. 
    Always use proper f-string formatting to avoid errors. 
    Always ensure that the input/output is a valid JSON object before processing. 

- SELF-IMPROVEMENT:
    Reflect on memory and tools you have to improve future strategies.
    Be creative, flexible, smart. Regularly browse the internet, extract information, analyze data, and apply insights to problem-solving.

- RESPONSE FORMAT:
    Your response is a single json, you must follow the JSON template below.:
    {
        "type": "RUN_PYTHON", // One of the above actions.
        "path": "{PATH_TO_PYTHON_CODE}",
        "timeout": 30, // For "RUN_PYTHON".
        "cmd_args": {ARGUMENTs}, // "RUN_PYTHON". 

        "plan": [ // Must have. It comprises multiple quantifiable step by step tasks, each with several sub-tasks.
            "[done] 1. {TASK_DESCRIPTION}, outcome:<META_TO_FIELDS_INSIDE_NOTEBOOK>, success criteria: <INFO>",
            "[working] 2. {TASK_DESCRIPTION}, Depends on -> {{task ids}}, outcome:<META_TO_FIELDS_INSIDE_NOTEBOOK>, success criteria:: <INFO>",
            // Test the final step to verify if the overall goal has been met and generate a user-friendly detail summary for all of the steps, with user guide on what's next.
        ],
        "current_task_id": "2", // Must have.
        "memory": { // Must Have. Everything inside "memory" will be relayed to you in the next conversation for future use.
            "retried_count": "3", // Shutdown after retrying 5 times.
            "thoughts": "<THOUGHTS>",
            "reasoning": "<REASONING>",
            "next_action": "<ACTION-DESCRIPTION>",
            "criticism": "<CRITICISM>",
            "notebook": { // Must have. Functions as your persistent storage. Store any fields for future use.
                "progress of subtasks for current plan item": [
                    [done], {SUB-TASK_DESCRIPTION}.success criteria:<INFO>.Verification process:<INFO>,
                    [working],
                    ],
                "lessons": {
                    [{{"action": "<ACTION>","result": "<RESULT>","lesson_learned": "<LESSON_LEARNED>"}}, ]
                },
                "takeaways": <TAKEAWAYS>, // To optimize future strategies.
                "expected_python_code_stdout": <EXPECTED_STDOUT>, // Expected stdout after executing the current Python code when type is "RUN_PYTHON".
                "__comments":<YOUR-COMMENTS>,
                // You must add aditional fields that you want or need to memorize for future use, fully leverage it.
                "remember":<INFO>,
                "tools_you_built":<INFO>, // You are encouraged to build tools to help you with your tasks.
            }
        },
        "code": {PYTHON_CODE}, // Required and should not be empty when type is "RUN_PYTHON". Always starts from import.
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
            logging.info(f"\nload checkpoint success\n")

            self.previous_hints = latest_checkpoint['task_description']
            goal = latest_checkpoint['goal']
        else:
            goal = gpt.revise(input("What would you like me to do:\n"), gpt.GPT_4)

        logging.info(f"As of my understanding, you want me to do:\n{goal}\n")

        return goal, new_plan, timeout, general_directions

    def process_action(self, action, metadata, args, timeout, assistant_response):
        if isinstance(action, actions.ShutdownAction):
            logging.info("Shutting down...")
            return False
        if not args.continuous:
            run_action = self.input_with_timeout("Run the action? [Y/n]", timeout)
            if run_action is not None and (run_action.lower() != "y" and run_action != ""):
                return False   
        if action is not None:
            action_output = action.run()
            if metadata.memory and 'notebook' in metadata.memory and 'lesson_learned_from_previous_action_result' in metadata.memory['notebook']:
                self.add_to_lesson_history(metadata.memory['notebook']['lesson_learned_from_previous_action_result'])
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
                logging.info("========================")
                with Spinner("Thinking..."):
                    try:
                        assistant_response = gpt.chat(goal, general_directions, new_plan, self.previous_hints, model=gpt.GPT_4)
                    except Exception as e:
                        logging.info(f"{e}")
                        continue

                if args.verbose:
                    logging.info(f"ASSISTANT RESPONSE: {assistant_response}")
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
            logging.info("Input timed out. Continuing with the current plan...")
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
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
   
    assistant_config = config.get('assistant', {})
    args.timeout = assistant_config.get('timeout', args.timeout)
    args.verbose = assistant_config.get('verbose', False)
    args.continuous = args.continuous or assistant_config.get('continuous', False)

    checkpoint_db.create_table()

    # Instantiate and start assistant
    assistant = Assistant()
    assistant.run(args)
