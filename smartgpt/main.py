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
    def __init__(self, instruction, act, goal):
        self.instruction = instruction
        self.act = act
        self.goal = goal

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
            end = args["query"].find("End##")
            if start != -1 and end != -1:
                args["query"] = args["query"][:start] + args["query"][end+len("##End"):]
            args["query"] = self.eval_value(args["query"])

        if action_type == "ExtractInfo":
            args["url"] = self.eval_value(args["url"])

        if action_type == "RunPython":
            # if file_name is empty, use the default file
            file_name = args.get("file_name")
            if file_name is None or file_name == "":
                args["file_name"] = f"tmp_{action_id}.py"
            # if timeout is empty, use the default timeout
            timeout = args.get("timeout")
            if timeout is None or timeout == "":
                args["timeout"] = 30

        if action_type in ["TextCompletion"]:
            args = self.handle_jarvisvm_methods(args, action_type)
            if action_type == "TextCompletion":
                args["prompt"] = f"our goal:{self.goal}\nYou are working on one of the steps to archive the goal.\n {args['prompt']}"

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

    def handle_jarvisvm_methods(self, args, action_type):
        target_arg = "prompt"
        text = args[target_arg]
        args[target_arg] = self.eval_value(text)
        return args

    def eval_value(self, text):
        pattern = re.compile(r"\{\{(.*?)\}\}")
        matches = pattern.findall(text)
        logging.info(f"\eval_value(), matches: {matches}, text:{text}\n")
        for match in matches:
            if 'jarvisvm.' in match and "jarvisvm.set" not in match:
                evaluated = eval(match)
                logging.info(f"\nevaluated: {evaluated}, code:{match}\n")
                text = text.replace("{{" + f"{match}" + "}}", str(evaluated), 1)
        
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
        }

    def run(self, instrs, goal):
        while self.pc < len(instrs):
            instruction = Instruction(instrs[self.pc], self.actions, goal)
            action_type = instrs[self.pc].get("type")
            if action_type == "If":
                self.conditional(instruction)
            elif action_type == "Loop":
                self.loop(instruction)
            else:
                instruction.execute()
            self.pc += 1

    def loop(self, instr):
        args = instr.instruction["args"]
        # Extract the count and the list of instructions for the loop
        loop_count = args["count"]
        # remove the first {{ and last }} from loop_count
        if loop_count.startswith("{{") and loop_count.endswith("}}"):
            loop_count = loop_count[2:-2]
            # loop_count needs to be evaluated in the context of jarvisvm
            loop_count = eval(loop_count)
            logging.info(f"loop_count: {loop_count}")
        loop_instructions = instr.instruction.get("args", {}).get("instructions", [])
        logging.info(f"Looping: {loop_instructions}")


        # Execute the loop instructions the given number of times
        old_pc = self.pc
        for i in range(loop_count):
            # Set the loop index in jarvisvm, to adopt gpt behaviour error
            jarvisvm.set("loop_index", i)
            jarvisvm.set("index", i)
            jarvisvm.set("i", i)
            # As each loop execution should start from the first instruction, we reset the program counter
            self.pc = 0
            self.run(loop_instructions, instr.goal)
        self.pc = old_pc + len(loop_instructions)

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
    parser.add_argument('--continuous', action='store_true', help='Continuous mode')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--json', type=str, help='Path to the JSON file to execute plan from')
    parser.add_argument('--startseq', type=int, default=0, help='Starting sequence number')

    args = parser.parse_args()

    # Load configuration from YAML file
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)


    # Logging file name and line number
       
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        stream=sys.stdout
    )

    logging.info("Welcome to Jarvis, your personal assistant for everyday tasks!\n")

    assistant_config = config.get('assistant', {})
    args.timeout = args.timeout or assistant_config.get('timeout', 30)
    args.verbose = args.verbose or assistant_config.get('verbose', False)
    args.continuous = args.continuous or assistant_config.get('continuous', False)

    os.makedirs("workspace", exist_ok=True)
    os.chdir("workspace")

    jarvisvm.load_kv_store()
    actions.load_cache()

    # If a JSON file path is provided, load the plan_with_instrs from the JSON file, otherwise generate a new plan_with_instrs
    if args.json:
        # Load the plan_with_instrs from the JSON file
        with open(args.json, 'r') as f:
            plan_with_instrs = json.load(f)
    else:
        # Generate a new plan
        planner.gen_instructions(base_model, replan=False)

        # load 1.json
        with open("1.json", 'r') as f:
            plan_with_instrs = json.load(f)

    # Find the starting sequence number
    start_seq = args.startseq
    logging.info(f"plan_with_instrs: {plan_with_instrs['instructions']}")

    # Make sure start_seq is within bounds
    if start_seq < 0 or start_seq >= len(plan_with_instrs["instructions"]):
        print(f"Invalid start sequence number: {start_seq}")
        exit(1)

    # Run the instructions starting from start_seq
    interpreter = JarvisVMInterpreter()
    logging.info(f"Running instructions from  {plan_with_instrs['instructions'][start_seq]}\n")
    interpreter.run(plan_with_instrs["instructions"][start_seq:], goal=plan_with_instrs["goal"])





    
