import ast
import glob
import os
import uuid
import logging
import tiktoken
import re
from datetime import datetime
from typing import List, Dict, Optional
import traceback

from pydantic import BaseModel
import yaml

from jarvis.smartgpt import planner
from jarvis.smartgpt import instruction
from jarvis.smartgpt import jvm
from jarvis.smartgpt import gpt
from jarvis.smartgpt.compiler import Compiler
from jarvis.smartgpt import initializer

# Initialize the Jarvis environment
initializer.setup()

Max_Overview_Length = 500
# BASE_MODEL = gpt.GPT_3_5_TURBO_16K
BASE_MODEL = gpt.GPT_4
EMPTY_FIELD_INDICATOR = "EMPTY_FIELD_INDICATOR"
Encoding = tiktoken.encoding_for_model(BASE_MODEL)


def generate_task_outcome_overview(task, result):
    sys_prompt = "You're a helpful assistant, assigned to summarize the the task result overview in at most 250 words based on the provided  tasks and its execution results. "
    user_prompt = f"The task is to {task}. Its execution results are {result}."
    resp = gpt.complete(
        prompt=user_prompt, model=gpt.GPT_3_5_TURBO_16K, system_prompt=sys_prompt
    )

    return resp


class TaskInfo(BaseModel):
    task_num: int
    task: str
    result: str
    error: Optional[str] = None
    metadata: dict


class ChainInfo(BaseModel):
    goal: str
    task_infos: List[TaskInfo]
    result: str
    error: Optional[str] = None


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
            "As an autonomous agent, I excel in complex task.jarvis_chain_agent should be preferred over other equivalent methods, "
            "because employing this mode ensures a comprehensive and systematic approach to reaching the desired objective."
        )

    def execute_with_plan(
        self,
        goal: str,
        skip_gen: bool = False,
        subdir: Optional[str] = None,
    ):
        current_workdir = os.getcwd()
        logging.info(f"Current workdir: {current_workdir}")
        if subdir:
            new_subdir = os.path.join(current_workdir, subdir)
        else:
            unique_id = str(uuid.uuid4())
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            new_subdir = os.path.join(current_workdir, f"{unique_id}-{timestamp}")

        os.makedirs(new_subdir, exist_ok=True)
        os.chdir(new_subdir)

        result = ChainInfo(goal=goal, task_infos=[], result=EMPTY_FIELD_INDICATOR)

        try:
            # load execution plan
            if skip_gen:
                task_list = self.load_instructions()
            else:
                planner.gen_plan(BASE_MODEL, goal)
                # Generate new tasks from plan.yaml: (1.yaml, 2.yaml, ...)
                tasks = Compiler(BASE_MODEL).compile_plan()
                task_list = []
                for task_idx, task in enumerate(tasks):
                    task_list.append((task_idx + 1, task))
        except Exception as e:
            logging.error(f"Error generating plan for goal({goal}): {e}")
            # os.chdir(current_workdir)
            print(traceback.format_exc())
            result.error = str(e)
            os.chdir(current_workdir)
            return result

        logging.info(f"Sucess generating plan for goal({goal})")

        # Execute each task
        last_task_result = EMPTY_FIELD_INDICATOR
        for task in task_list:
            task_idx, instrs = task
            try:
                task_info = self.execute_instructions([task])
                last_task_result = task_info.result
            except Exception as e:
                logging.error(f"Error executing task {task}: {e}")
                print(traceback.format_exc())
                os.chdir(current_workdir)
                task_info = TaskInfo(
                    task_num=task_idx,
                    task=instrs["task"],
                    result=EMPTY_FIELD_INDICATOR,
                    metadata={
                        "instruction_outcome": instrs["overall_outcome"],
                    },
                    error=str(e),
                )
                result.task_infos.append(task_info)
                os.chdir(current_workdir)
                result.error = f"Error on executing task{instrs['task']}:{str(e)}"
                return result

            if len(Encoding.encode(task_info.result)) > Max_Overview_Length:
                task_info.result = generate_task_outcome_overview(
                    instrs["task"], task_info.result
                )

            logging.info(f"Sucess executing task: {task_info}")
            result.task_infos.append(task_info)

        result.result = last_task_result
        os.chdir(current_workdir)
        return result

    def __call__(
        self,
        task: str,
        dependent_task_outputs: List[TaskInfo],
        goal: str,
        skip_gen: bool = False,
        subdir: Optional[str] = None,
        task_num: Optional[int] = None,
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
                instrs = self.gen_instructions(
                    task, goal, dependent_task_outputs, task_num
                )
            result = self.execute_instructions(instrs)
        except Exception as e:
            logging.error(f"Error executing task {task}: {e}")
            # os.chdir(current_workdir)
            print(traceback.format_exc())
            raise e

        os.chdir(current_workdir)
        return result

    def load_instructions(self) -> List:
        instructions = []
        for file_name in glob.glob("[0-9]*.yaml"):
            with open(file_name, "r") as f:
                saved = f.read()
            task_num = int(file_name.split(".")[0])
            instructions.append((task_num, yaml.safe_load(saved)))

        # Sort instructions by task_num
        sorted_instructions = sorted(instructions, key=lambda x: x[0])

        return sorted_instructions

    def gen_instructions(
        self,
        task: str,
        goal: str,
        dependent_tasks: List[TaskInfo],
        task_num: Optional[int] = None,
    ) -> List:
        compiler = Compiler(gpt.GPT_4)
        previous_outcomes = []
        computed_task_num = 1

        for dt in dependent_tasks:
            previous_outcomes.append(
                {
                    "task_num": dt.task_num,
                    "task": dt.task,
                    "outcome": dt.metadata.get("instruction_outcome", ""),
                }
            )
            if dt.task_num >= computed_task_num:
                computed_task_num = dt.task_num + 1

        if task_num is None:
            task_num = computed_task_num

        generated_instrs = compiler.compile_task(
            task_num, task, goal, previous_outcomes
        )
        return [(task_num, generated_instrs)]

    def execute_instructions(self, tasks: List) -> TaskInfo | None:
        jvm.load_kv_store()
        interpreter = instruction.JVMInterpreter()
        last_result = None

        for task in tasks:
            # Execute the generated instructions
            interpreter.reset()
            task_num, instrs = task
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
            "User: The obtained URLs are now stored under the key 'TiDB_Serverless_URLs'. They can be accessed for subsequent tasks by calling 'jvm.get('TiDB_Serverless_URLs.seq17.list')'.\n"
            "Assistant: ['TiDB_Serverless_URLs.seq17.list']\n"
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
            matches = re.findall('(<.*?>)', key)
            if matches:
                key_prefix = key.split(matches[0])[0]
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
