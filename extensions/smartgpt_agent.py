import glob
import shutil
import sys
import os
import re
import uuid
import logging

import yaml

from smartgpt import actions
from smartgpt import planner
from smartgpt import instruction
from smartgpt import jvm
from smartgpt import gpt

BASE_MODEL = gpt.GPT_3_5_TURBO_16K

os.makedirs("workspace", exist_ok=True)
os.chdir("workspace")

# Logging file name and line number
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    filename='smartgpt.log', # Log output goes to this file
    filemode='a' # Append to the file instead of overwriting it
)

def execute_task(objective: str, task: str, context: list) -> str:
    sys_prompt = (
        f"As a sophisticated AI agent, you are required to perform a task based on the following objective: {objective}.\n\n"
    )
    if context:
        sys_prompt += "Consider these previously completed tasks:\n" + "\n".join(context) + "\n\n"

    sys_prompt += (
        "Before you execute the given task, consider whether it is a complex task "
        "(like requiring internet access, file I/O, or others that exceed LLM's capabilities). "
        "If it is yes, you MUST respond with template: 'call_smartgpt_exec(<one_sentence_task_summary, no json>), reasoning: <why_choose_smartgpt>'. "
        "Otherwise, for the simple task you can execute it and respond directly.\n\n"
    )

    sys_prompt += (
        "Note: smartgpt is an automated agent (auto-agent) that can decompose a complex goal into multiple sub-tasks and execute them. "
        "The call_smartgpt_exec() is the entry point of smartgpt."
    )

    prompt = f'Your current task is: {task}\nYour response: '
    result = gpt.complete(prompt, BASE_MODEL, sys_prompt)

    match = re.match(r"call_smartgpt_exec\(['\"]?(.*?)['\"]?\)", result)
    if match:
        smartgpt_goal = match.group(1)
        return call_smartgpt_exec(smartgpt_goal)

    return result


def call_smartgpt_exec(goal: str) -> str:
    # Generate the unique run_id of each smartgpt agent execution
    run_id = f"smartgpt.{uuid.uuid4()}"

    # Reset kv store
    jvm.reset_kv_store()
    actions.disable_cache()

    goal = f"{goal}, the overall outcome should be written into a file named 'smartgpt.out'."

    # Generate a new plan
    planner.gen_instructions(model=BASE_MODEL, replan=True, goal=goal)

    # Generate new tasks from plan.yaml: (1.yaml, 2.yaml, ...)
    task_count = planner.gen_instructions(BASE_MODEL, replan=False)

    for i in range(task_count):
        # Load the plan_with_instrs from the task YAML file
        with open(f"{i + 1}.yaml", 'r') as f:
            plan_with_instrs = yaml.safe_load(f)

        # Execute the task
        interpreter = instruction.JVMInterpreter()
        interpreter.run(plan_with_instrs["instructions"], task=plan_with_instrs["task"])

    # todo: extract the final Outcome from the kv store
    result = "smartgpt task run failed."
    if os.path.exists("smartgpt.out"):
        with open("smartgpt.out", 'r') as f:
            result = f.read()

    # Cleanup
    if not os.path.exists(run_id):
        os.makedirs(run_id)

    for file_name in glob.glob("*.yaml"):
        shutil.move(file_name, run_id)

    for file_name in glob.glob("run_*.py"):
        shutil.move(file_name, run_id)

    return result
