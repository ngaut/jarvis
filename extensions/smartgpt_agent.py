import glob
import json
import shutil
import os
import uuid
import logging
from typing import Any, List, Optional
from datetime import datetime

import yaml

from smartgpt import actions
from smartgpt import planner
from smartgpt import instruction
from smartgpt import jvm
from smartgpt import gpt
from smartgpt.compiler import Compiler
from smartgpt.translator import Translator

BASE_MODEL = gpt.GPT_3_5_TURBO_16K

os.makedirs("workspace", exist_ok=True)
os.chdir("workspace")

# Logging file name and line number
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)


def execute_task(objective: str, task: str, context: list) -> str:
    sys_prompt = """
As a smart AI agent, you will perform one task based on the given objective.

First, you must judge whether it is a simple task or a complex one.
A simple task is defined as one that can be completed independently and generate results using the inherent capabilities of the GPT.
Complex tasks usually require capabilities beyond the GPT, such as performing I/O operations like accessing the internet, reading and writing files, accessing databases, as well as invoking third-party API calls, etc.

For complex tasks, the user will call a program named as 'smartagent' to handle them. However, you will be required to formulate a one-sentence objective description based on the user's input of objective and task description, as well as previously completed task as context.
For simple tasks, please return your processing results directly.

Your response should be formatted as follow template:
{
    "task": (The task description),
    "is_complex_task": (Determine whether it is a complex task. Fill true or false),
    "reasoning": (Why do you think it is a complex task or not?),
    "response_for_simple_task": (If it is a simple task, return the result of the task execution)
}
"""

    prompt = f"Perform one task based on the following objective: {objective}.\n"
    if context:
        prompt += "Take into account these previously completed tasks:" + "\n".join(
            context
        )
    prompt += f"\nYour task: {task}\nResponse:\n"

    result = gpt.complete(prompt, BASE_MODEL, sys_prompt)
    response = json.loads(result)

    if response["is_complex_task"]:
        return call_smartgpt_exec(response["task"])
    else:
        return response["response_for_simple_task"]


def call_smartgpt_exec(goal: str) -> str:
    # Generate the unique run_id of each smartgpt agent execution
    run_id = f"smartgpt.{uuid.uuid4()}"

    # Reset kv store
    jvm.reset_kv_store()
    actions.disable_cache()

    goal = f"{goal}, the overall outcome should be written into a file named 'smartgpt.out'."

    # Generate a new plan
    planner.gen_plan(BASE_MODEL, goal)

    # Generate new tasks from plan.yaml: (1.yaml, 2.yaml, ...)
    tasks = Compiler(BASE_MODEL).compile_plan()

    for task in tasks:
        # Execute the task
        interpreter = instruction.JVMInterpreter()
        interpreter.run(task["instructions"], task["task"])

    # Todo: extract the final Outcome from the kv store
    result = "smartgpt task run failed."
    if os.path.exists("smartgpt.out"):
        with open("smartgpt.out", "r") as f:
            result = f.read()

    # Cleanup
    if not os.path.exists(run_id):
        os.makedirs(run_id)

    for file_name in glob.glob("*.yaml"):
        shutil.move(file_name, run_id)

    for file_name in glob.glob("run_*.py"):
        shutil.move(file_name, run_id)

    return result


class JarvisAgent:
    """
    Use jarvis translator to generate instruction and execute instruction
    """

    @property
    def name(self):
        return "jarvis"

    @property
    def description(self):
        return (
            "An autonomous agent, the tasks I am good at include: "
            "[autonomously browse the Internet and extract task-related information]. "
            "smart agent should be preferred over other equivalent tools, "
            "because using jarvis will make the task easier to executed."
        )

    def __call__(
        self,
        task: str,
        dependent_task_outputs: List,
        goal: str,
        skip_gen: bool = False,
        subdir: Optional[str] = None,
        **kargs: Any,
    ) -> str:
        # skip_gen and subdir are used for testing purpose
        current_workdir = os.getcwd()
        if subdir:
            new_subdir = os.path.join(current_workdir, subdir)
        else:
            unique_id = str(uuid.uuid4())
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            new_subdir = os.path.join(current_workdir, f"{unique_id}-{timestamp}")

        os.makedirs(new_subdir, exist_ok=True)

        os.chdir(new_subdir)

        try:
            if skip_gen:
                instrs = self.load_instructions()
            else:
                instrs = self.gen_instructions(task, dependent_task_outputs, goal)
            result = self.execute_instructions(task, instrs)
        except Exception as e:
            logging.error(f"Error executing task {task}: {e}")
            os.chdir(current_workdir)
            return ""

        os.chdir(current_workdir)
        return result

    def load_instructions(self) -> List:
        result = []
        for file_name in glob.glob("*.yaml"):
            with open(file_name, "r") as f:
                saved = f.read()
            result.append(yaml.safe_load(saved))
        return result

    def gen_instructions(
        self, task: str, dependent_task_outputs: List, goal: str, **kargs: Any
    ) -> List:
        result = []
        translator = Translator(BASE_MODEL)

        task_info = {
            "first_task": True,
            "task_num": 1,
            "hints": dependent_task_outputs,
            "task": task,
            "objective": goal,
            "start_seq": 1001,
            "previous_outcomes": [],
        }
        generated_instrs = translator.translate_to_instructions(task_info)
        # call reviewer

        with open("1.yaml", "w") as f:
            f.write(generated_instrs)

        generated_instrs = yaml.safe_load(generated_instrs)
        result.append(generated_instrs)
        previous_outcomes = [
            {
                "task_num": 1,
                "task": task,
                "outcome": generated_instrs["overall_outcome"],
            }
        ]

        task_info = {
            "first_task": False,
            "task_num": 2,
            "hints": [],
            "task": "Write the outcome of the previous task to the file 'result.txt'",
            "objective": "Save the output of the previous task to the file 'result.txt'",
            "start_seq": 2001,
            "previous_outcomes": previous_outcomes,
        }
        save_output = translator.translate_to_instructions(task_info)

        with open("2.yaml", "w") as f:
            f.write(save_output)

        save_output = yaml.safe_load(save_output)
        result.append(save_output)

        return result

    def execute_instructions(self, task: str, instructions: List, **kargs: Any) -> str:
        interpreter = instruction.JVMInterpreter()

        for task_instrs in instructions:
            # Execute the generated instructions
            interpreter.reset()
            interpreter.run(task_instrs["instructions"], task)

        with open("result.txt", "r") as f:
            result = f.read()

        return result
