from typing import Optional
from dotenv import load_dotenv
from spinner import Spinner
import response_parser, check_point, gpt
from actions import SearchOnlineAction, ExtractInfoAction, RunPythonAction, TextCompletionAction

import os, sys, time, re, signal, argparse, logging
import ruamel.yaml as yaml
from datetime import datetime
import planner

base_model  = gpt.GPT_3_5_TURBO

import json

class JarvisVMInterpreter:
    def __init__(self):
        self.result_register = {}
        self.pc = 0
        self.actions = {
            "SearchOnline": SearchOnlineAction,
            "ExtractInfo": ExtractInfoAction,
            "RunPython": RunPythonAction,
            "TextCompletion": TextCompletionAction
        }

    def run(self, instructions):
        while self.pc < len(instructions):
            instruction = instructions[self.pc]
            action_type = instruction.get("type")
            if action_type == "If":
                self.conditional(instruction)
            else:
                self.execute_instruction(instruction)
            self.pc += 1

    def execute_instruction(self, instruction):
        action_type = instruction.get("type")
        action_class = self.actions.get(action_type)
        if action_class is None:
            print(f"Unknown action type: {action_type}")
            return

        action_id = instruction.get("seqnum")
        action = action_class(action_id, **instruction.get("args", {}))
        result = action.run()
        
        # Store result in result register if specified
        set_result_register = instruction.get("SetResultRegister")
        if set_result_register is not None:
            self.result_register[set_result_register["key"]] = result

    def conditional(self, instruction):
        condition_text = instruction["GetResultRegister"]
        condition = instruction["condition"]
        prompt = f'Does the text "{condition_text}" meet the condition "{condition}"?'
        f'Please provide your answer as a JSON-formatted response with fields "result" (true or false) and "reasoning" (the reasoning behind your decision).'

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
            self.execute_instruction(instruction["then"])
        else:
            self.pc = instruction["else"]["seqnum"]



instructions = [
    {
        "seqnum": 1,
        "type": "SearchOnline",
        "query": "Weather in San Francisco",
        "SetResultRegister": {
            "key": "WeatherInfo",
            "value": "ResultOfSearch"
        },
        "action_id": 1
    },
    {
        "seqnum": 2,
        "type": "ExtractInfo",
        "url": "https://www.weather.com/weather/today/l/USCA0987:1:US",
        "instructions": "Please find the current temperature in San Francisco",
        "SetResultRegister": {
            "key": "WeatherInfo",
            "value": "ResultOfExtraction"
        },
        "action_id": 2
    },
    {
        "seqnum": 3,
        "type": "If",
        "GetResultRegister": "WeatherInfo",
        "condition": "'Weather information' found",
        "then": {
            "seqnum": 4,
            "type": "RunPython",
            "file_name": "generate_report.py",
            "code": """
import datetime
date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"Weather report as of {date}: \\nTemperature in San Francisco: {temp}")
            """,
            "SetResultRegister": {
                "key": "WeatherReport",
                "value": "ResultOfPythonRun"
            },
            "action_id": 3
        },
        "else": {
            "seqnum": 5,
            "type": "TextCompletion",
            "prompt": "Sorry, we couldn't find the weather information.",
            "SetResultRegister": {
                "key": "WeatherReport",
                "value": "ResultOfCompletion"
            },
            "action_id": 4
        },
        "action_id": 5
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
