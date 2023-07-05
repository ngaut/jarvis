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
    stream=sys.stdout
)

def execute_task(objective: str, task: str, context: list) -> str:
    sys_prompt = (
        f"As a sophisticated AI agent, you are required to perform a task based on the following objective: {objective}.\n"
    )
    if context:
        sys_prompt += 'Consider these previously completed tasks: ' + '\n - ' + '\n - '.join(context) + '\n'

    sys_prompt += (
        'Before you execute the given task, analyze whether it is complex (like requiring internet access, file I/O, '
        'or tasks that exceed LLM\'s capabilities). If it is, must respond with: "call_smartgpt_exec(<summarize_the_task_goal>)". '
        "Otherwise, for a simpler task you should execute it and respond the result."
    )

    prompt = f'Your current task is: {task}\n Your response: '
    result = gpt.complete(prompt, BASE_MODEL, sys_prompt)

    match = re.match(r"call_smartgpt_exec\((['\"]?)(.*?)\1\)", result)
    if match:
        smartgpt_goal = match.group(1)
        return call_smartgpt_exec(smartgpt_goal)

    return result


def call_smartgpt_exec(goal: str) -> str:
    # Generate the unique run_id of each smartgpt agent execution
    run_id = f"smartgpt.{uuid.uuid4()}"

    # Reset kv store
    jvm.load_kv_store()
    actions.disable_cache()

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
        interpreter.run(plan_with_instrs["instructions"], goal=plan_with_instrs["goal"])

    # todo: extract the final Outcome from the kv store
    result = ""

    # Cleanup
    if not os.path.exists(run_id):
        os.makedirs(run_id)

    for file_name in glob.glob("*.yaml"):
        shutil.move(file_name, run_id)

    for file_name in glob.glob("run_*.py"):
        shutil.move(file_name, run_id)

    return result
