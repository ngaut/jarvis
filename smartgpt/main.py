from typing import Optional
from dotenv import load_dotenv
from spinner import Spinner
import gpt, jarvisvm
import actions

import os, sys, time, re, signal, argparse, logging, pprint
import ruamel.yaml as yaml
from datetime import datetime
import planner
import json

base_model  = gpt.GPT_3_5_TURBO


class Instruction:
    def __init__(self, instruction, act):
        self.instruction = instruction
        self.act = act

    def execute(self):
        logging.info(f"instruction: {self.instruction}\n")
        action_type = self.instruction.get("type")

        action_class = self.act.get(action_type)
        if action_class is None:
            print(f"Unknown action type: {action_type}")
            return

        action_id = self.instruction.get("seqnum")
        args = self.instruction.get("args", {})

        # patch ExtractInfoAction
        if action_type == "ExtractInfo":
            urls = jarvisvm.get("urls")
            # extract urls, remove '[' and ']' from the string
            urls = urls[1:-1].split(',')
            url = urls[0].strip()
            url = url[1:-1]
            logging.info(f"ExtractInfoAction: url: {url}\n")
            args["url"] = url  # update the url in the arguments

        # patch prompt by replacing jarvisvm.get('key') with value using regex
        if action_type == "TextCompletion":
            # use regex to extract key from result:{jarvisvm.get('key')}
            pattern = re.compile(r"jarvisvm.get\('(\w+)'\)")
            prompt = args["prompt"]
            matches = pattern.findall(prompt)
            for match in matches:
                key = match
                value = jarvisvm.get(key)
                logging.info(f"Get '{key}' = '{value}'\n")
                # replace jarvisvm.get('...') in prompt with value
                args["prompt"] = prompt.replace(f"jarvisvm.get('{key}')", value, 1)


        # Use from_dict to create the action object
        action_data = {"type": action_type, "action_id": action_id}
        action_data.update(args)
        logging.info(f"execute instruction: %s\n", action_data)

        action = actions.Action.from_dict(action_data)
        if action is None:
            print(f"Failed to create action from data: {action_data}")
            return

        result = action.run()

        logging.info(f"result: {result}\n")

        if action_type != "RunPython":
            # use regex to extract key and value from result:{jarvisvm.set('key', '<TEXT>')}
            pattern = re.compile(r"jarvisvm.set\('(\w+)', '(.*)'\)")
            matches = pattern.findall(result)

            for match in matches:
                key = match[0]
                value = match[1]
                jarvisvm.set(key, value)
                logging.info(f"Set '{key}' = '{value}'\n")

        
class JarvisVMInterpreter:
    def __init__(self):
        self.pc = 0
        self.actions = {
            "SearchOnline": actions.SearchOnlineAction,
            "ExtractInfo": actions.ExtractInfoAction,
            "RunPython": actions.RunPythonAction,
            "TextCompletion": actions.TextCompletionAction,
            "Shutdown": actions.ShutdownAction,
        }

    def run(self, instructions):
        while self.pc < len(instructions):
            instruction = Instruction(instructions[self.pc], self.actions)
            action_type = instructions[self.pc].get("type")
            if action_type == "If":
                self.conditional(instruction)
            else:
                instruction.execute()
            self.pc += 1

    def conditional(self, instruction):
        condition = instruction.instruction.get("args", {}).get("condition", None)
        prompt = f'Is that true?: "{condition}"? Please respond in the following JSON format: \n{{"result": "true/false", "reasoning": "your reasoning"}}.'

        # patch prompt by replacing jarvisvm.get('key') with value using regex
        # use regex to extract key from result:{jarvisvm.get('key')}    
        pattern = re.compile(r"jarvisvm.get\('(\w+)'\)")
        matches = pattern.findall(prompt)
        for match in matches:
            key = match
            value = jarvisvm.get(key)
            # replace jarvisvm.get('...') in prompt with value
            prompt = prompt.replace(f"jarvisvm.get('{key}')", value, 1)
        evaluation_result = actions.TextCompletionAction(0, prompt).run()

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
            # instruction.instruction["then"] is a list of instructions
            self.run(instruction.instruction["then"])
        else:
            instrs = instruction.instruction["else"]
            if instrs is not None:
                # maybe use pc to jump is a better idea.
                self.run(instrs)



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

    os.makedirs("workspace", exist_ok=True)
    os.chdir("workspace")

    plan = planner.gen_instructions(base_model)
    # parse the data between left and right brackets
    start = plan.find('{')
    end = plan.rfind('}')
    if end < start:
        logging.info(f"invalid json:%s\n", plan)
        exit(1)
    plan = json.loads(plan[start:end+1])
    instructions = plan["instructions"]
    interpreter = JarvisVMInterpreter()
    interpreter.run(instructions)

    
