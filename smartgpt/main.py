from typing import Optional
from dotenv import load_dotenv
from spinner import Spinner
import gpt
import actions

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
    def __init__(self, instruction, act, result_register):
        self.instruction = instruction
        self.act = act
        self.result_register = result_register

    def execute(self):
        action_type = self.instruction.get("type")

        action_class = self.act.get(action_type)
        if action_class is None:
            print(f"Unknown action type: {action_type}")
            return

        logging.info(f"instruction: %s\n", self.instruction)
        action_id = self.instruction.get("seqnum")

        # set os env for python action
        if action_type == "RunPython":
            # set os env with the result register
            for key, value in self.result_register.register.items():
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
            self.instruction["args"]["url"] = url  # update the url in the arguments

        # Use from_dict to create the action object
        action_data = {"type": action_type, "action_id": action_id}
        action_data.update(self.instruction.get("args", {}))
        action = actions.Action.from_dict(action_data)
        if action is None:
            print(f"Failed to create action from data: {action_data}")
            return

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
            "SearchOnline": actions.SearchOnlineAction,
            "ExtractInfo": actions.ExtractInfoAction,
            "RunPython": actions.RunPythonAction,
            "TextCompletion": actions.TextCompletionAction
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

    plan = planner.gen_instructions(base_model)
    # parse the data between left and right brackets
    start = plan.find('{')
    end = plan.rfind('}')
    if end < start:
        logging.info(f"invlid json:%s\n", plan)
        exit(1)
    plan = plan[start+1:end]
    instructions = json.loads(plan)["instructions"]
    interpreter = JarvisVMInterpreter()
    interpreter.run(instructions)

    
