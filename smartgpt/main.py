from typing import Optional
from dotenv import load_dotenv
from spinner import Spinner
import gpt
from actions import SearchOnlineAction, ExtractInfoAction, RunPythonAction, TextCompletionAction

import os, sys, time, re, signal, argparse, logging
import ruamel.yaml as yaml
from datetime import datetime
import planner

base_model  = gpt.GPT_3_5_TURBO

import json

class ResultRegister:
    def __init__(self):
        self.register = {}

    def get(self, key):
        return self.register.get(key)

    def set(self, key, value):
        self.register[key] = value

class Instruction:
    def __init__(self, instruction, actions, result_register):
        self.instruction = instruction
        self.actions = actions
        self.result_register = result_register

    def execute(self):
        action_type = self.instruction.get("type")

        action_class = self.actions.get(action_type)
        if action_class is None:
            print(f"Unknown action type: {action_type}")
            return

        logging.info(f"instruction: %s\n", self.instruction)
        action_id = self.instruction.get("seqnum")

        # set os env for python action
        if action_type == "RunPython":
            # set os env with the result register
            for key, value in self.result_register.register.items():
                logging.info(f"Set os env: {key} = {value}\n")
                os.environ[key] = value

         # patch ExtractInfoAction
        if action_type == "ExtractInfo":
            key = self.instruction["args"]["urls"]["GetResultRegister"]
            urls = self.result_register.get(key)
            # extract urls, remove '[' and ']' from the string
            urls = urls[1:-1].split(',')
            url = urls[0].strip()
            url = url[1:-1]
            logging.info(f"ExtractInfoAction: url: {url}\n")
            action = action_class(action_id, url=url, instructions=self.instruction["args"]["instructions"])
        else:
            action = action_class(action_id, **self.instruction.get("args", {}))

        result = action.run()
        
        # Store result in result register if specified
        set_result_register = self.instruction.get("SetResultRegister", None)
        if set_result_register is not None:
            for kv in set_result_register["kvs"]:
                if kv["value"] == "$FILL_LATER":
                    kv["value"] = result
                self.result_register.set(kv["key"], kv["value"])
        logging.info(f"current result_register: {set_result_register}\n")


class JarvisVMInterpreter:
    def __init__(self):
        self.result_register = ResultRegister()
        self.pc = 0
        self.actions = {
            "SearchOnline": SearchOnlineAction,
            "ExtractInfo": ExtractInfoAction,
            "RunPython": RunPythonAction,
            "TextCompletion": TextCompletionAction
        }

    def run(self, instructions):
        while self.pc < len(instructions):
            instruction = Instruction(instructions[self.pc], self.actions, self.result_register)
            action_type = instructions[self.pc].get("type")
            if action_type == "If":
                self.conditional(instruction)
            else:
                result = instruction.execute()
            self.pc += 1

    def conditional(self, instruction):
        #logging.info("Conditional instruction: %s", instruction.instruction)
        condition_text = self.result_register.get(instruction.instruction.get("args", {}).get("GetResultRegister", None))
        condition = instruction.instruction.get("args", {}).get("condition", None)
        prompt = f'Does the text "{condition_text}" meet the condition "{condition}"? Please respond in the following JSON format: \n{{"result": "true/false", "reasoning": "your reasoning"}}.'

        evaluation_result = TextCompletionAction(0, prompt).run()

        try:
            result_json = json.loads(evaluation_result)
            condition = result_json.get('result', False)
            reasoning = result_json.get('reasoning', '')
        except json.JSONDecodeError:
            condition = False
            reasoning = ''
            print(f"Failed to decode AI model response into JSON: {evaluation_result}")

        print(f"Condition evaluated to {condition}. Reasoning: {reasoning}")

        if condition:
            instruction = Instruction(instruction.instruction["then"], self.actions, self.result_register)
            result = instruction.execute()
        else:
            self.pc = instruction.instruction["else"]["seqnum"]

instructions = [
    {
        "seqnum": 1,
        "type": "SearchOnline",
        "args": {
            "query": "temperature in San Francisco"
        },
        "SetResultRegister": {
            "kvs":[{"key": "UrlList", "value": "$FILL_LATER"}],
            "__constraint__": "key must be 'UrlList', result must be a list of URLs"
        }
    },
    {
        "seqnum": 2,
        "type": "ExtractInfo",
        "args": {
            "urls": {
                "GetResultRegister": "UrlList"
            },
            "instructions": "Extrace the current temperature in San Francisco from the following content, and return me a json with the format: {'San Francisco':[{'key':'temperature', 'value': 'temperature_value'}, {'key': 'date', 'value': 'date_value'}]}"
        },
        "SetResultRegister": {
            "kvs":[{"key": "temperature", "value": "$FILL_LATER"}, {"key": "date", "value": "FILL_LATER"}],
            "__constraint__": "key name must match with generated python code bellow"
        }
    },
    {
        "seqnum": 3,
        "type": "If",
        "args": {
            "GetResultRegister": "temperature",
            "condition": "'Current temperature in San Francisco' found"
        },
        "then": {
            "seqnum": 4,
            "type": "RunPython",
            "args": {
                "file_name": "generate_report.py",
                "code": "import datetime\nimport os\n\ntemp = os.environ.get('temperature')\ndate = os.environ.get('date')\nprint(f\"Weather report as of {date}: \nTemperature in San Francisco: {temp}\")"
            },
            "SetResultRegister": {
                "kvs":[{"key": "WeatherReport", "value": "$FILL_LATER(output of generate_report.py)"}]
            }
        },
        "else": {
            "seqnum": 5,
            "type": "Shutdown",
            "args": {
                "summary": "Weather report could not be generated as we couldn't find the weather information for San Francisco."
            }
        }
    }
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to the configuration file')
    parser.add_argument('--timeout', type=int, default=1, help='Timeout for user input')  
    parser.add_argument('--continuous', action='store_true', help='Continuous mode')  # Add this line
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')

    args = parser.parse_args()

    # Load configuration from YAML file
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

 
    # Logging configuration
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)

    logging.info("Welcome to Jarvis, your personal assistant for everyday tasks!\n")
   
    assistant_config = config.get('assistant', {})
    args.timeout = args.timeout or assistant_config.get('timeout', 30)
    args.verbose = args.verbose or assistant_config.get('verbose', False)
    args.continuous = args.continuous or assistant_config.get('continuous', False)

    interpreter = JarvisVMInterpreter()
    interpreter.run(instructions)

   # planner.gen_instructions(base_model)
