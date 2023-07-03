import os
import sys
import argparse
import logging
import yaml
from dotenv import load_dotenv

from smartgpt import actions
from smartgpt import planner
from smartgpt import gpt
from smartgpt import jvm
from smartgpt import instruction

BASE_MODEL = gpt.GPT_3_5_TURBO_16K

class JVMInterpreter:
    def __init__(self):
        self.pc = 0
        self.actions = {
            "WebSearch": actions.WebSearchAction,
            "Fetch": actions.FetchAction,
            "RunPython": actions.RunPythonAction,
            "TextCompletion": actions.TextCompletionAction,
        }

        jvm.set_loop_idx(0)

    def run(self, instrs, goal):
        if instrs is not None:
            while self.pc < len(instrs):
                jvm_instr = instruction.JVMInstruction(instrs[self.pc], self.actions, goal)
                action_type = instrs[self.pc].get("type")
                if action_type == "If":
                    self.conditional(jvm_instr)
                elif action_type == "Loop":
                    self.loop(jvm_instr)
                else:
                    jvm_instr.execute()
                self.pc += 1

    def loop(self, jvm_instr: instruction.JVMInstruction):
        args = jvm_instr.instruction["args"]
        # Extract the count and the list of instructions for the loop
        loop_count = args["count"]
        # if loop_count is integer
        if isinstance(loop_count, int):
            loop_count = loop_count
        elif isinstance(loop_count, str):
            # loop_count needs to be evaluated in the context of jvm
            loop_count = int(jvm.eval(loop_count))

        loop_instructions = jvm_instr.instruction.get("args", {}).get("instructions", [])
        logging.info(f"Looping: {loop_instructions}")

        # Execute the loop instructions the given number of times
        old_pc = self.pc
        for i in range(loop_count):
            # Set the loop index in jvm, to adopt gpt behaviour error
            jvm.set_loop_idx(i)
            logging.info(f"loop idx: {i}")
            # As each loop execution should start from the first instruction, we reset the program counter
            self.pc = 0
            self.run(loop_instructions, jvm_instr.goal)
        self.pc = old_pc

    def conditional(self, jvm_instr: instruction.JVMInstruction):
        condition = jvm_instr.instruction.get("args", {}).get("condition", None)
        condition = jvm_instr.eval_and_patch(condition)
        output_fmt = {
            "kvs": [
                {"key": "result", "value": "<to_fill>"},
                {"key": "reasoning", "value": "<to_fill>"},
            ]
        }
        evaluation_action = actions.TextCompletionAction(
            -1,
            "Is that true or false?",
            condition,
            yaml.safe_dump(output_fmt))

        def str_to_bool(s):
            if s.lower() == 'true':
                return True
            elif s.lower() == 'false':
                return False
            else:
                return False

        try:
            evaluation_result = evaluation_action.run()
            output_res = yaml.safe_load(evaluation_result)
            condition_eval_result = str_to_bool(output_res["kvs"][0]["value"])
            condition_eval_reasoning = output_res["kvs"][1]["value"]

        except Exception as err:
            condition_eval_result = False
            condition_eval_reasoning = ''
            logging.critical(f"Failed to decode AI model response: {condition} with error: {err}")

        logging.info(f"Condition evaluated to {condition_eval_result}. Reasoning: {condition_eval_reasoning}")

        if condition_eval_result:
            # instruction.instruction["then"] is a list of instructions
            self.run(jvm_instr.instruction["then"], jvm_instr.goal)
        else:
            # maybe use pc to jump is a better idea.
            self.run(jvm_instr.instruction["else"], jvm_instr.goal)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to the configuration file')
    parser.add_argument('--timeout', type=int, default=1, help='Timeout for user input')
    parser.add_argument('--continuous', action='store_true', help='Continuous mode')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--replan', action='store_true', help='create a new plan')
    parser.add_argument('--yaml', type=str, help='Path to the yaml file to execute plan from')
    parser.add_argument('--startseq', type=int, default=0, help='Starting sequence number')

    args = parser.parse_args()

    load_dotenv()

    # Load configuration from YAML file
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # Logging file name and line number
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        stream=sys.stdout
    )

    print("Welcome to Jarvis, your personal assistant for everyday tasks!\n")

    assistant_config = config.get('assistant', {})
    args.timeout = args.timeout or assistant_config.get('timeout', 30)
    args.verbose = args.verbose or assistant_config.get('verbose', False)
    args.continuous = args.continuous or assistant_config.get('continuous', False)
    args.replan = args.replan or assistant_config.get('replan', False)

    os.makedirs("workspace", exist_ok=True)
    os.chdir("workspace")

    jvm.load_kv_store()
    actions.load_cache()

    # If a YAML file path is provided, load the plan_with_instrs from the YAML file, otherwise generate a new plan_with_instrs
    if args.yaml:
        # Load the plan_with_instrs from the YAML file
        with open(args.yaml, 'r') as f:
            plan_with_instrs = yaml.safe_load(f)
    else:
        # Generate a new plan
        planner.gen_instructions(BASE_MODEL, replan=args.replan)
        exit(0)

    # Find the starting sequence number
    start_seq = args.startseq
    logging.info(f"plan_with_instrs: {plan_with_instrs['instructions']}")

    # Make sure start_seq is within bounds
    if start_seq < 0 or start_seq >= len(plan_with_instrs["instructions"]):
        print(f"Invalid start sequence number: {start_seq}")
        exit(1)

    # Run the instructions starting from start_seq
    logging.info(f"Running instructions from  {plan_with_instrs['instructions'][start_seq]}\n")

    interpreter = JVMInterpreter()
    interpreter.run(plan_with_instrs["instructions"][start_seq:], goal=plan_with_instrs["goal"])
