import logging
import yaml

from smartgpt import actions
from smartgpt import jvm

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

        if action_type == "WebSearch":
            args["save_to"] = self.eval_and_patch(args["save_to"])

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
            args["command"] = self.eval_and_patch(args["command"])
            args["content"] = self.eval_and_patch(args["content"])
            args["output_fmt"] = self.eval_and_patch(yaml.safe_dump(args["output_fmt"]))

        action_data = {"type": action_type, "action_id": action_id}
        action_data.update(args)

        action = actions.Action.from_dict(action_data)
        if action is None:
            print(f"Failed to create action from data: {action_data}")
            return

        logging.info(f"Running action: {action}\n")
        result = action.run()
        logging.info(f"\nresult of {action_type}: {result}\n")

        if action_type != "RunPython":
            # todo: handle error if the result is not a yaml
            self.post_exec(result)

    def eval_and_patch(self, text):
        while True:
            tmp_text = jvm.eval(text)
            if tmp_text is None:
                break
            text = tmp_text
        """
        # find the substring starts with {'kvs': or {"kvs": and ends with }]
        match = re.search(r"\{['\"]kvs['\"]:(.+)\]\}", text)

        if match is not None:
            resp_format = match.group(0)
            logging.info(f"resp_format: {resp_format}\n")

            def replace(match):
                key_expr = match.group(2)

                if "jvm.get" in key_expr:
                    to_eval = utils.wrap_string_to_eval(key_expr)
                    logging.info(f"to_eval: {to_eval}")
                    patched_key = f"'{utils.eval_expression(to_eval)}'"
                    return f'{match.group(1)}:{patched_key}, {match.group(3)}:{match.group(4)}'
                else:
                    logging.info(f"key: {key_expr} is not a dynamic key, no need to eval")
                    return match.group(0)

            # pattern that handles both single and double quoted strings for 'key', 'value', and their corresponding values
            pattern = re.compile(r"('key'|\"key\"):\s*('.+?'|\".+?\"),\s*('value'|\"value\"):\s*('.+?'|\".+?\")")
            text = text.replace(resp_format, pattern.sub(replace, resp_format))
        """
        return text

    def post_exec(self, result: str):
        try:
            data = yaml.safe_load(result)
        except yaml.YAMLError as err:
            logging.error(f"Failed to parse YAML: {result}, error: {str(err)}")
            return

        # Check if "kvs" key exists in the YAML
        if "kvs" not in data:
            logging.error(f"No 'kvs' key in the YAML: {result}")
            return

        # Iterate over key-value pairs and set them in the jvm
        for kv in data["kvs"]:
            try:
                key = kv["key"]
                value = kv["value"]
            except KeyError:
                logging.error(f"Invalid kv item in the YAML: {kv}")
                continue

            logging.info(f"Setting key-value: {kv} in the JVM")
            jvm.set(key, value)
