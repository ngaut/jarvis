import ast
import glob
import json
import shutil
import os
import uuid
import logging
from datetime import datetime
from pydantic import BaseModel
from typing import Any, List, Dict, Optional
import traceback
import yaml
import time

from smartgpt import actions
from smartgpt import planner
from smartgpt import instruction
from smartgpt import jvm
from smartgpt import gpt
from smartgpt.compiler import Compiler
from smartgpt.translator import Translator

# BASE_MODEL = gpt.GPT_3_5_TURBO_16K
BASE_MODEL = gpt.GPT_4
EMPTY_FIELD_INDICATOR = "EMPTY_FIELD_INDICATOR"

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


class TaskInfo(BaseModel):
    task_num: int
    task: str
    result: str
    metadata: dict


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
        dependent_task_outputs: List[TaskInfo],
        goal: str,
        skip_gen: bool = False,
        subdir: Optional[str] = None,
        **kargs: Any,
    ) -> TaskInfo | None:
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
                instrs = self.gen_instructions(task, goal, dependent_task_outputs)
            result = self.execute_instructions(instrs)
        except Exception as e:
            logging.error(f"Error executing task {task}: {e}")
            os.chdir(current_workdir)
            print(traceback.format_exc())
            raise e

        os.chdir(current_workdir)
        return result

    def load_instructions(self) -> Dict:
        instructions = {}
        for file_name in glob.glob("*.yaml"):
            with open(file_name, "r") as f:
                saved = f.read()
            task_num = int(file_name.split(".")[0])
            instructions[task_num] = yaml.safe_load(saved)
        return instructions

    def gen_instructions(
        self, task: str, goal: str, dependent_tasks: List[TaskInfo]
    ) -> Dict:
        compiler = Compiler(BASE_MODEL)
        previous_outcomes = []
        task_num = 1

        for dt in dependent_tasks:
            previous_outcomes.append(
                {
                    "task_num": dt.task_num,
                    "task": dt.task,
                    "outcome": dt.metadata.get("instruction_outcome", ""),
                }
            )
            if dt.task_num >= task_num:
                task_num = dt.task_num + 1

        hints = [
            f"The current task is a part of the gloal goal: {goal}",
        ]

        generated_instrs = compiler.compile_task(
            task_num, task, hints, previous_outcomes
        )
        return {task_num: generated_instrs}

    def execute_instructions(self, instructions: Dict) -> TaskInfo | None:
        jvm.load_kv_store()
        interpreter = instruction.JVMInterpreter()
        last_result = None

        for task_num, instrs in instructions.items():
            # Execute the generated instructions
            interpreter.reset()
            logging.info(f"Executing task {task_num}: {instrs}")
            interpreter.run(instrs["instructions"], instrs["task"])
            last_result = TaskInfo(
                task_num=task_num,
                task=instrs["task"],
                result=EMPTY_FIELD_INDICATOR,
                metadata={
                    "instruction_outcome": instrs["overall_outcome"],
                },
            )

        if last_result is not None:
            result = self.get_task_result(last_result.metadata["instruction_outcome"])
            if result is not None and result != "None":
                last_result.result = result

        return last_result

    def get_task_result(self, overall_outcome: str, return_key: bool = False):
        sys_prompt = (
            "You're a helpful assistant, please output the keys (in python list type) where the overall task output result is stored according to the task output description.\n"
            "Examples:\n"
            "User: The data under the key 'AI_trends' has been analyzed and 1-3 projects that have shown significant trends or growth have been selected. The selected projects have been stored in the database under the key 'selected_projects.seq2.list'.\n"
            "Assistant: ['selected_projects.seq2.list']\n"
            "User: The trending AI projects information from the last 28 days has been extracted. The descriptions of the selected projects for the tweet can be retrieved with keys like 'project_description_<idx>.seq4.str'.\n"
            "Assistant: ['project_description_<idx>.seq4.str']\n"
            "User: The top 3 projects based on their advancements and growth rate have been selected. The projects can be retrieved with keys 'top_project_0.seq19.str', 'top_project_1.seq19.str', and 'top_project_2.seq19.str'. These projects will be featured in the tweet for their recent advancements and high growth rate.\n"
            "Assistant: ['top_project_0.seq19.str', 'top_project_1.seq19.str', 'top_project_2.seq19.str']\n"
        )
        user_prompt = overall_outcome

        resp = gpt.complete(
            prompt=user_prompt, model=gpt.GPT_3_5_TURBO_16K, system_prompt=sys_prompt
        )

        # for testing purpose
        if return_key:
            return resp

        keys = ast.literal_eval(resp)
        result = None
        for key in keys:
            if "<idx>" in resp:
                key_prefix = key.split("<idx>")[0]
                res = jvm.eval(
                    f'jvm.eval(jvm.list_values_with_key_prefix("{key_prefix}"))'
                )
            else:
                res = jvm.eval(f'jvm.eval(jvm.get("{key}"))')
            if res is not None and res != "None":
                if result is None:
                    result = str(res)
                else:
                    result += f"\n{key}:{res}"

        return result
