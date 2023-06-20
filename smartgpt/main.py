from typing import Optional
from dotenv import load_dotenv
from spinner import Spinner
import gpt, jvm
import actions
import ast

import os, sys, time, re, signal, argparse, logging, pprint
import ruamel.yaml as yaml
from datetime import datetime
import planner
import json

base_model  = gpt.GPT_3_5_TURBO

LAZY_EVAL_PREFIX = "@eval("

    
def eval_expression(text, lazy_eval_prefix=LAZY_EVAL_PREFIX):
    logging.info(f"enter eval_expression\n")
    # find last occurrence of "@eval("
    start = text.rfind(lazy_eval_prefix)
    if start == -1:
        return None

    prefix_len = len(lazy_eval_prefix)
    # find the corresponding closing tag with parentheses balance
    rest = text[start+prefix_len:]
    balance = 0
    end = 0
    for char in rest:
        if char == '(':
            balance += 1
        elif char == ')':
            if balance == 0:
                break
            balance -= 1
        end += 1

    if balance != 0:
        logging.critical(f"Error: parentheses are not balanced in {text}")
        return None

    logging.info(f"eval_and_patch_template_before_exec, {start}-{end} text: {text}\n")

    # adjust the end position relative to the original string
    end = end + start + prefix_len
    # evaluate the substring between @eval( and )
    expression = text[start+prefix_len:end].strip()
    try:
        evaluated = eval(expression)
    except Exception as e:
        logging.critical(f"Failed to evaluate {expression}. Error: {str(e)}")
        return None

    # replace the evaluated part in the original string
    text = text[:start] + str(evaluated) + text[end+1:]
    logging.info(f"text after patched: {text}\n")

    return text

def fix_string_to_json(s):
    # fix single quotes to double quotes
    s = s.replace("'", '"')
    return s


def set_idx_in_jvm(value):
    jvm.set("idx", value)
    jvm.set("index", value)
    jvm.set("i", value)

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

        action_id = self.instruction.get("seq")
        # clone the args dict!
        args = dict(self.instruction.get("args"))

        if action_type == "SearchOnline": 
            # extract key from: {"kvs":[{"key":"search_results.seq1.list", "value": "<to_fill>"}]}
            resp_format = args["resp_format"]
            if resp_format is not None:
                # find and decode json to extract key
                start = resp_format.find("{")
                end = resp_format.rfind("}")
                if start != -1 and end != -1:
                    resp_format = resp_format[start:end+1]
                    resp_format = json.loads(resp_format)
                    # get the key
                    key = resp_format["kvs"][0]["key"]
                    # replace the value with the key
                    args["result_key"] = key

        if action_type == "ExtractInfo":
            # patch instruction
            args["command"] = self.eval_and_patch_before_exec(args["command"])

        if action_type == "Fetch":
            args["url"] = self.eval_and_patch_before_exec(args["url"])
            args["save_to"] = self.eval_and_patch_before_exec(args["save_to"])

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
            args["prompt"] = self.eval_and_patch_before_exec(args["prompt"])

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
            # todo: handle error if the result is not a json 
            self.patch_after_exec(result)

    

    def eval_and_patch_before_exec(self, text):
        while True:
            tmp_text = eval_expression(text)
            if tmp_text is None:
                break
            text = tmp_text

        logging.info(f"\n*************text before patched: *********************\n")
        patch_success = False
        start = text.find("{'kvs':")
        end = text.rfind("}")
        if start != -1 and end != -1:
            resp_format = text[start:end+1]
            logging.info(f"resp_format: {resp_format}\n")
            # todo: need to enhance the regex to support more complex cases
            pattern = re.compile(r"'key':\s*(.+?),\s*'value':\s*(.+?)")
            matches = pattern.findall(resp_format)

            new_resp_format = resp_format
            for match in matches:
                key = match[0]
                if key.find("jvm.get") == -1: # not a dynamic key, no need to eval
                    logging.info(f"key: {key} is not a dynamic key, no need to eval\n")
                    continue
                # patch the key
                # add LAZY_EVAL_PREFIX and ")" to the wrapped key
                to_eval = LAZY_EVAL_PREFIX + key + ")"
                logging.info(f"to_eval: {to_eval}\n")
                patched_key = eval_expression(to_eval, lazy_eval_prefix=LAZY_EVAL_PREFIX)
                # replace the key with the patched one 
                # todo: may have side effectives.
                text = text.replace(key, patched_key, 1)
                patch_success = True

            # from 'start' to replace single quotes to double quotes 
            text = text[:start] + fix_string_to_json(text[start:])


        return text
    
    def patch_after_exec(self, result):
        # parse result that starts with first '{' and ends with last '}' as json
        start = result.find("{")
        end = result.rfind("}")
        
        if start != -1 and end != -1:
            logging.info(f"patch_after_exec**********\n")
            result = result[start:end+1]
            result = json.loads(result)
            # get the key and value pair list
            for kv in result["kvs"]:
                logging.info(f"patch_after_exec, set kv: {kv}\n")
                jvm.set(kv["key"], kv["value"])

        
class JVMInterpreter:
    def __init__(self):
        self.pc = 0
        self.actions = {
            "SearchOnline": actions.SearchOnlineAction,
            "Fetch": actions.FetchAction,
            "ExtractInfo": actions.ExtractInfoAction,
            "RunPython": actions.RunPythonAction,
            "TextCompletion": actions.TextCompletionAction,
        }

        set_idx_in_jvm(0)

    def run(self, instrs, goal):
        while self.pc < len(instrs):
            instruction = Instruction(instrs[self.pc], self.actions, goal)
            action_type = instrs[self.pc].get("type")
            if action_type == "If":
                self.conditional(instruction, goal)
            elif action_type == "Loop":
                self.loop(instruction)
            else:
                instruction.execute()
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
            loop_count = int(eval_expression(loop_count))
        loop_instructions = instr.instruction.get("args", {}).get("instructions", [])
        logging.info(f"Looping: {loop_instructions}")


        # Execute the loop instructions the given number of times
        old_pc = self.pc
        for i in range(loop_count):
            # Set the loop index in jvm, to adopt gpt behaviour error
            set_idx_in_jvm(i)
            logging.info(f"idx: {i}")
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





    
