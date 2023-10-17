import json
import logging

from jarvis.smartgpt import actions
from jarvis.smartgpt import jvm
from jarvis.smartgpt import utils


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
        # clone the args dict!
        args = dict(self.instruction.get("args"))

        if action_type == "WebSearch":
            args["query"] = self.eval_and_patch(args["query"])
            args["save_to"] = self.eval_and_patch(args["save_to"])

        if action_type == "FetchWebContent":
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
            args["request"] = self.eval_and_patch(args.get("request"))
            args["content"] = self.eval_and_patch(args.get("content"))
            args["output_format"] = self.eval_and_patch(
                json.dumps(args.get("output_format"), indent=2)
            )

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
            self.post_exec(result)
        else:
            jvm.load_kv_store()

    def eval_and_patch(self, text) -> str:
        if text is None:
            return ""

        while True:
            tmp_text = jvm.eval(text)
            if tmp_text is None:
                break
            text = tmp_text

        return text

    def post_exec(self, result: str):
        try:
            data = json.loads(result)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse: {result}, error: {e}")
            raise

        # Check if "kvs" key exists in the result
        if "kvs" not in data:
            logging.error(f"No 'kvs' in the result: {result}")
            return

        # Iterate over key-value pairs and set them in the jvm
        for kv in data["kvs"]:
            try:
                key = kv["key"]
                value = kv["value"]
            except KeyError:
                logging.error(f"Invalid KV item in the result: {kv}")
                return

            logging.info(f"Setting KV in the JVM database: '{key}'={value}")
            jvm.set(key, value)


class JVMInterpreter:
    def __init__(self):
        self.pc = 0
        self.actions = {
            "WebSearch": actions.WebSearchAction,
            "FetchWebContent": actions.FetchWebContentAction,
            "RunPython": actions.RunPythonAction,
            "TextCompletion": actions.TextCompletionAction,
        }

        jvm.load_kv_store()
        actions.disable_cache()
        actions.load_cache()
        jvm.set_loop_idx(0)

    def run(self, instrs, task):
        if instrs is not None:
            while self.pc < len(instrs):
                logging.info(
                    f"Running Instruction [pc={self.pc}, seq={instrs[self.pc].get('seq')}]: \n{instrs[self.pc]}"
                )
                jvm_instruction = JVMInstruction(instrs[self.pc], self.actions, task)

                action_type = instrs[self.pc].get("type")
                if action_type == "If":
                    self.conditional(jvm_instruction)
                elif action_type == "Loop":
                    self.loop(jvm_instruction)
                else:
                    jvm_instruction.execute()
                self.pc += 1

    def loop(self, jvm_instruction: JVMInstruction):
        args = jvm_instruction.instruction.get("args", {})
        # Extract the count and the list of instructions for the loop
        loop_count = 0
        # if loop_count is integer
        logging.info(
            f"loop instruction (seq={jvm_instruction.instruction.get('seq', 'N/A')}) args: {args}"
        )
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
            # logging.info(f"loop idx: {i}")
            # As each loop execution should start from the first instruction, we reset the program counter
            self.pc = 0
            self.run(loop_instructions, jvm_instruction.task)
        self.pc = old_pc

    def conditional(self, jvm_instruction: JVMInstruction):
        condition = jvm_instruction.instruction.get("args", {}).get("condition", None)
        condition = jvm_instruction.eval_and_patch(condition)

        evaluation_action = actions.TextCompletionAction(
            action_id=-1,
            request="Judging true or false based on input content",
            content=condition,
            output_format=json.dumps(
                {"kvs": [{"key": "result.seq0.bool", "value": "<to_fill>"}]}, indent=2
            ),
        )

        try:
            evaluation_result = evaluation_action.run()
            output_res = json.loads(evaluation_result)
            condition_eval_result = utils.str_to_bool(output_res["kvs"][0]["value"])

        except Exception as err:
            logging.error(
                f"Failed to decode AI model response: {condition} with error: {err}"
            )
            raise

        logging.info(f"The condition is evaluated to {condition_eval_result}.")

        old_pc = self.pc
        if condition_eval_result:
            # instruction.instruction["then"] is a list of instructions
            if "then" in jvm_instruction.instruction.get("args", {}):
                self.pc = 0
                self.run(
                    jvm_instruction.instruction["args"]["then"], jvm_instruction.task
                )
        else:
            # maybe use pc to jump is a better idea.
            if "else" in jvm_instruction.instruction.get("args", {}):
                self.pc = 0
                self.run(
                    jvm_instruction.instruction["args"]["else"], jvm_instruction.task
                )
        self.pc = old_pc

    def reset(self):
        self.pc = 0
        jvm.set_loop_idx(0)
