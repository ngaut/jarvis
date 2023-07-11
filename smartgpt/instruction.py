import logging
import yaml

from smartgpt import actions
from smartgpt import jvm
from smartgpt import utils


class JVMInstruction:
    def __init__(self, instruction, act, task):
        self.instruction = instruction
        self.act = act
        self.task = task

    def execute(self):
        action_type = self.instruction.get("type")

        action_class = self.act.get(action_type)
        if action_class is None:
            print(f"Unknown action type: {action_type}")
            return

        action_id = self.instruction.get("seq")
        objective = self.instruction.get("objective")
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
            args["command"] = self.eval_and_patch(args.get("command"))
            args["content"] = self.eval_and_patch(args.get("content"))
            args["output_fmt"] = self.eval_and_patch(yaml.safe_dump(args.get("output_fmt")))
            args["objective"] = objective

        action_data = { "type": action_type, "action_id": action_id }
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

    def eval_and_patch(self, text) -> str:
        if text is None:
            return "None"

        while True:
            tmp_text = jvm.eval(text)
            if tmp_text is None:
                break
            text = tmp_text

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

    def run(self, instrs, task):
        if instrs is not None:
            while self.pc < len(instrs):
                jvm_instr = JVMInstruction(instrs[self.pc], self.actions, task)
                action_type = instrs[self.pc].get("type")
                if action_type == "If":
                    self.conditional(jvm_instr)
                elif action_type == "Loop":
                    self.loop(jvm_instr)
                else:
                    jvm_instr.execute()
                self.pc += 1

    def loop(self, jvm_instr: JVMInstruction):
        args = jvm_instr.instruction.get("args", {})
        # Extract the count and the list of instructions for the loop
        loop_count = 0
        # if loop_count is integer
        if isinstance(args["count"], int):
            loop_count = args["count"]
        elif isinstance(args["count"], str):
            if args["count"].isdigit():
                loop_count = int(args["count"])
            else:
                # loop_count needs to be evaluated in the context of jvm
                loop_count = jvm.eval(args["count"])
                if loop_count is None:
                    loop_count = 0
                else:
                    loop_count = int(loop_count)

        loop_instructions = args.get("instructions", [])
        logging.debug(f"Looping: {loop_instructions}")

        # Execute the loop instructions the given number of times
        old_pc = self.pc
        for i in range(loop_count):
            # Set the loop index in jvm, to adopt gpt behaviour error
            jvm.set_loop_idx(i)
            logging.info(f"loop idx: {i}")
            # As each loop execution should start from the first instruction, we reset the program counter
            self.pc = 0
            self.run(loop_instructions, jvm_instr.task)
        self.pc = old_pc

    def conditional(self, jvm_instr: JVMInstruction):
        condition = jvm_instr.instruction.get("args", {}).get("condition", None)
        condition = jvm_instr.eval_and_patch(condition)
        output_fmt = {
            "kvs": [
                {"key": "result", "value": "<to_fill>"},
                {"key": "reasoning", "value": "<to_fill>"},
            ]
        }

        evaluation_action = actions.TextCompletionAction(
            action_id = -1,
            objective="Evaluate true and false based on input content",
            command = "Is that true or false?",
            content = condition,
            output_fmt = yaml.safe_dump(output_fmt))

        try:
            evaluation_result = evaluation_action.run()
            output_res = yaml.safe_load(evaluation_result)
            condition_eval_result = utils.str_to_bool(output_res["kvs"][0]["value"])
            condition_eval_reasoning = output_res["kvs"][1]["value"]

        except Exception as err:
            condition_eval_result = False
            condition_eval_reasoning = ''
            logging.critical(f"Failed to decode AI model response: {condition} with error: {err}")

        logging.info(f"Condition evaluated to {condition_eval_result}. Reasoning: {condition_eval_reasoning}")

        old_pc = self.pc
        if condition_eval_result:
            # instruction.instruction["then"] is a list of instructions
            if "then" in jvm_instr.instruction.get("args", {}):
                self.pc = 0
                self.run(jvm_instr.instruction["args"]["then"], jvm_instr.task)
        else:
            # maybe use pc to jump is a better idea.
            if "else" in jvm_instr.instruction.get("args", {}):
                self.pc = 0
                self.run(jvm_instr.instruction["args"]["else"], jvm_instr.task)
        self.pc = old_pc
