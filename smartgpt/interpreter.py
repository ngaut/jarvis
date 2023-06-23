import json
import logging
import re

from smartgpt import actions
from smartgpt import jvm
from smartgpt import utils

class JVMInstruction:
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
            args["save_to"] = self.eval_and_patch(args["save_to"])

        if action_type == "ExtractInfo":
            # patch instruction
            args["command"] = self.eval_and_patch(args["command"])
            args["content"] = self.eval_and_patch(args["content"])
            args["output_fmt"] = self.eval_and_patch(args["output_fmt"])

        if action_type == "Fetch":
            args["url"] = self.eval_and_patch(args["url"])
            args["save_to"] = self.eval_and_patch(args["save_to"])

        if action_type == "RunPython":
            # if file_name is empty, use the default file
            file_name = args.get("file_name")
            if file_name is None or file_name == "":
                args["file_name"] = f"tmp_{action_id}.py"
            # if timeout is empty, use the default timeout
            timeout = args.get("timeout")
            if timeout is None or timeout == "":
                args["timeout"] = 30

        if action_type == "TextCompletion":
            args["prompt"] = self.eval_and_patch(args["prompt"])

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
            self.post_exec(result)

    def eval_and_patch(self, text):
        while True:
            tmp_text = utils.eval_expression(text)
            if tmp_text is None:
                break
            text = tmp_text

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
                to_eval = utils.wrap_string_to_eval(key)
                logging.info(f"to_eval: {to_eval}\n")
                patched_key = utils.eval_expression(to_eval)
                # replace the key with the patched one
                # todo: may have side effectives.
                text = text.replace(key, patched_key, 1)
                patch_success = True

            # from 'start' to replace single quotes to double quotes
            text = text[:start] + utils.fix_string_to_json(text[start:])

        return text
    
    def post_exec(self, result):
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
