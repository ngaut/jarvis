from typing import Optional
from dotenv import load_dotenv
from spinner import Spinner
import gpt, jarvisvm
import actions
import ast

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
        action_type = self.instruction.get("type")

        action_class = self.act.get(action_type)
        if action_class is None:
            print(f"Unknown action type: {action_type}")
            return

        action_id = self.instruction.get("seqnum")
        args = self.instruction.get("args", {})

        if action_type == "SearchOnline":
            # empty everything between ##Start and ##End
            start = args["query"].find("##Start")
            end = args["query"].find("##End")
            if start != -1 and end != -1:
                args["query"] = args["query"][:start] + args["query"][end+len("##End"):]
            args["query"] = self.modify_request_with_value(args["query"])

        if action_type == "ExtractInfo":
            urls = jarvisvm.get("urls")
            if urls:
                url = self.parse_url(urls)
                args["url"] = url

        if action_type == "RunPython":
            # if file_name is empty, use the default file
            file_name = args.get("file_name")
            if file_name is None or file_name == "":
                args["file_name"] = f"tmp_{action_id}.py"

        if action_type in ["TextCompletion", "Shutdown"]:
            args = self.handle_jarvisvm_methods(args, action_type)

        action_data = {"type": action_type, "action_id": action_id}
        action_data.update(args)

        # append action data to file
        with open("actions.json", "a") as f:
            f.write(json.dumps(action_data) + "\n")

        action = actions.Action.from_dict(action_data)
        if action is None:
            print(f"Failed to create action from data: {action_data}")
            return

        logging.info(f"Running action: {action}\n")
        result = action.run()
        logging.info(f"\nresult of {action_type}: {result}\n")

        if action_type != "RunPython":
            self.update_jarvisvm_values(result)

    def parse_url(self, urls):
        if len(urls) > 0:
            return urls[0]

    def handle_jarvisvm_methods(self, args, action_type):
        target_arg = "request" if action_type == "TextCompletion" else "summary"
        text = args[target_arg]
        args[target_arg] = self.modify_request_with_value(text)
        return args

    def modify_request_with_value(self, text):
        pattern = re.compile(r"\{\{(.*?)\}\}")
        matches = pattern.findall(text)
        logging.info(f"\nmodify request, matches: {matches}, text:{text}\n")
        for match in matches:
            if 'jarvisvm.' in match and "jarvisvm.set" not in match:
                evaluated = eval(match)
                logging.info(f"\nevaluated: {evaluated}, code:{match}\n")
                text = text.replace(f"{{{match}}}", str(evaluated), 1)
        
        return text


    def update_jarvisvm_values(self, result):
        pattern = re.compile(r"jarvisvm.set\('([^']*)', (.*?)\)")
        matches = pattern.findall(result)

        logging.info(f"\nupdate_jarvisvm_values, matches: {matches}, result:{result}\n")
        for match in matches:
            key = match[0]
            value_str = match[1].strip()
            try:
                value = ast.literal_eval(value_str)
            except (ValueError, SyntaxError):
                value = value_str.strip("'\"")
            jarvisvm.set(key, value)
            logging.info(f"\njarvisvm.set('{key}', {value})\n")


        
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
        request = f'Is that true?: "{condition}"? Please respond in the following JSON format: \n{{"result": "true/false", "reasoning": "your reasoning"}}.'

        # patch request by replacing jarvisvm.get('key') with value using regex
        # use regex to extract key from result:{jarvisvm.get('key')}    
        pattern = re.compile(r"jarvisvm.get\('(\w+)'\)")
        matches = pattern.findall(request)
        for match in matches:
            key = match
            value = jarvisvm.get(key)
            # replace jarvisvm.get('...') in request with value
            request = request.replace(f"jarvisvm.get('{key}')", value, 1)
        evaluation_result = actions.TextCompletionAction(0, request).run()

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
    parser.add_argument('--continuous', action='store_true', help='Continuous mode')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--json', type=str, help='Path to the JSON file to execute plan from')
    parser.add_argument('--startseq', type=int, default=0, help='Starting sequence number')

    args = parser.parse_args()

    # Load configuration from YAML file
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # Logging configuration
    # Logging with file name and line number
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

    logging.info("Welcome to Jarvis, your personal assistant for everyday tasks!\n")

    assistant_config = config.get('assistant', {})
    args.timeout = args.timeout or assistant_config.get('timeout', 30)
    args.verbose = args.verbose or assistant_config.get('verbose', False)
    args.continuous = args.continuous or assistant_config.get('continuous', False)

    os.makedirs("workspace", exist_ok=True)
    os.chdir("workspace")

    # If a JSON file path is provided, load the plan_with_instrs from the JSON file, otherwise generate a new plan_with_instrs
    if args.json:
        # Load the plan_with_instrs from the JSON file
        with open(args.json, 'r') as f:
            plan_with_instrs = json.load(f)
    else:
        # Generate a new plan
        plan_with_instrs = planner.gen_instructions(base_model)

        # parse the data between left and right brackets
        start = plan_with_instrs.find('{')
        end = plan_with_instrs.rfind('}')
        if end < start:
            logging.info(f"invalid json:%s\n", plan_with_instrs)
            exit(1)
        plan_with_instrs = json.loads(plan_with_instrs[start:end+1])
    
        # save the plan to a file
        with open('plan_with_instrs.json', "w") as f:
            json.dump(plan_with_instrs, f, indent=2)

    # Find the starting sequence number
    start_seq = args.startseq

    # Make sure start_seq is within bounds
    if start_seq < 0 or start_seq >= len(plan_with_instrs["instructions"]):
        print(f"Invalid start sequence number: {start_seq}")
        exit(1)

    # Run the instructions starting from start_seq
    interpreter = JarvisVMInterpreter()
    logging.info(f"Running instructions from  {plan_with_instrs['instructions'][start_seq]}\n")
    interpreter.run(plan_with_instrs["instructions"][start_seq:])




    
