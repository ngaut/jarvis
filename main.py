from typing import Optional
from dotenv import load_dotenv
import os, sys, re, argparse, logging
import ruamel.yaml as yaml
from datetime import datetime
import json

from smartgpt.spinner import Spinner
from smartgpt import actions
from smartgpt import planner
from smartgpt import utils
from smartgpt import gpt
from smartgpt import jvm
from smartgpt import instruction

base_model  = gpt.GPT_3_5_TURBO_16K

class JVMInterpreter:
    def __init__(self):
        self.pc = 0
        self.actions = {
            "WebSearch": actions.WebSearchAction,
            "Fetch": actions.FetchAction,
            "ExtractInfo": actions.ExtractInfoAction,
            "RunPython": actions.RunPythonAction,
            "TextCompletion": actions.TextCompletionAction,
        }

        jvm.set_loop_idx(0)

    def run(self, instrs, goal):
        while self.pc < len(instrs):
            ins = instruction.JVMInstruction(instrs[self.pc], self.actions, goal)
            action_type = instrs[self.pc].get("type")
            if action_type == "If":
                self.conditional(instruction, goal)
            elif action_type == "Loop":
                self.loop(ins)
            else:
                ins.execute()
            self.pc += 1

    def loop(self, instr):
        args = instr.instruction["args"]
        # Extract the count and the list of instructions for the loop
        loop_count = args["count"]
        # if loop_count is integer
        if isinstance(loop_count, int):
            loop_count = loop_count
        elif isinstance(loop_count, str):
            # loop_count needs to be evaluated in the context of jvm
            loop_count = int(utils.eval_expression(loop_count))
        loop_instructions = instr.instruction.get("args", {}).get("instructions", [])
        logging.info(f"Looping: {loop_instructions}")


        # Execute the loop instructions the given number of times
        old_pc = self.pc
        for i in range(loop_count):
            # Set the loop index in jvm, to adopt gpt behaviour error
            jvm.set_loop_idx(i)
            logging.info(f"loop idx: {i}")
            # As each loop execution should start from the first instruction, we reset the program counter
            self.pc = 0
            self.run(loop_instructions, instr.goal)
        self.pc = old_pc

    def conditional(self, instruction, goal):
        condition = instruction.instruction.get("args", {}).get("condition", None)
        prompt = f'Is that true?: "{condition}"? Please respond in the following JSON format: \n{{"result": "true/false", "reasoning": "your reasoning"}}.'

        # patch prompt by replacing jvm.get('key') with value using regex
        # use regex to extract key from result:{jvm.get('key')}    
        pattern = re.compile(r"jvm.get\('(\w+)'\)")
        matches = pattern.findall(prompt)
        for match in matches:
            key = match
            value = jvm.get(key)
            # replace jvm.get('...') in prompt with value
            prompt = prompt.replace(f"jvm.get('{key}')", value, 1)
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
            self.run(instruction.instruction["then"], goal)
        else:
            instrs = instruction.instruction["else"]
            if instrs is not None:
                # maybe use pc to jump is a better idea.
                self.run(instrs, goal)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to the configuration file')
    parser.add_argument('--timeout', type=int, default=1, help='Timeout for user input')
    parser.add_argument('--continuous', action='store_true', help='Continuous mode')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--replan', action='store_true', help='create a new plan')
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
    args.replan = args.replan or assistant_config.get('replan', False)

    os.makedirs("workspace", exist_ok=True)
    os.chdir("workspace")

    jvm.load_kv_store()
    actions.load_cache()

    # If a JSON file path is provided, load the plan_with_instrs from the JSON file, otherwise generate a new plan_with_instrs
    if args.json:
        # Load the plan_with_instrs from the JSON file
        with open(args.json, 'r') as f:
            plan_with_instrs = json.load(f)
    else:
        # Generate a new plan
        planner.gen_instructions(base_model, replan=args.replan)
        exit(0)

    # Find the starting sequence number
    start_seq = args.startseq
    logging.info(f"plan_with_instrs: {plan_with_instrs['instructions']}")

    # Make sure start_seq is within bounds
    if start_seq < 0 or start_seq >= len(plan_with_instrs["instructions"]):
        print(f"Invalid start sequence number: {start_seq}")
        exit(1)

    # Run the instructions starting from start_seq
    interpreter = JVMInterpreter()
    logging.info(f"Running instructions from  {plan_with_instrs['instructions'][start_seq]}\n")
    interpreter.run(plan_with_instrs["instructions"][start_seq:], goal=plan_with_instrs["goal"])
