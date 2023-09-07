import ast
import glob
import os
import uuid
import logging
import tiktoken
import re
import json

from datetime import datetime
from typing import List, Optional
import traceback

from pydantic import BaseModel
import yaml

from jarvis.smartgpt import initializer
from jarvis.smartgpt import planner
from jarvis.smartgpt import instruction
from jarvis.smartgpt import jvm
from jarvis.smartgpt import gpt
from jarvis.smartgpt.compiler import Compiler
from jarvis.extensions.skill import SkillManager
from jarvis.utils.tracer import conditional_chan_traceable


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


class JarvisExecutor:
    """
    Use jarvis translator to generate instruction and execute instruction
    """

    def __init__(self, executor_id: Optional[str] = None):
        self.completed_tasks = {}
        if executor_id is not None:
            self.executor_id = executor_id
        else:
            unique_id = str(uuid.uuid4())
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.executor_id = f"{unique_id}-{timestamp}"

    @conditional_chan_traceable(run_type="chain")
    def execute_with_plan(
        self,
        goal: str,
        skip_gen: bool = False,
    ):
        current_workdir = os.getcwd()
        logging.info(f"Current workdir: {current_workdir}")
        new_subdir = os.path.join(current_workdir, self.executor_id)
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
            logging.info(traceback.format_exc())
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
                logging.info(traceback.format_exc())
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
            self.completed_tasks[task_idx] = task_info

        result.result = last_task_result
        os.chdir(current_workdir)
        return result

    def execute(
        self,
        goal: str,
        task: str,
        task_num: Optional[int] = None,
        dependent_taskIDs: List = [],
        skip_gen: bool = False,
    ) -> TaskInfo | None:
        # skip_gen and subdir are used for testing purpose
        current_workdir = os.getcwd()
        new_subdir = os.path.join(current_workdir, self.executor_id)
        os.makedirs(new_subdir, exist_ok=True)
        os.chdir(new_subdir)

        previous_tasks = []
        for dt_id in dependent_taskIDs:
            previous_task = self.completed_tasks.get(dt_id, None)
            if previous_task is None:
                logging.error(f"Error: dependent task {dt_id} is not completed")
                os.chdir(current_workdir)
                raise Exception(
                    f"Error: depend task {dt_id} is not found under {self.executor_id}"
                )
            else:
                previous_tasks.append(previous_task)

        try:
            if skip_gen:
                instrs = self.load_instructions()
            else:
                instrs = self.gen_instructions(task, goal, previous_tasks, task_num)
            result = self.execute_instructions(instrs)
        except Exception as e:
            logging.error(f"Error executing task {task}: {e}")
            os.chdir(current_workdir)
            logging.error(traceback.format_exc())
            raise e

        os.chdir(current_workdir)
        if result is not None:
            self.completed_tasks[result.task_num] = result
        return result

    def eval_plan(self, goal: str, subdir: str):
        current_workdir = os.getcwd()
        new_subdir = os.path.join(current_workdir, subdir)
        os.chdir(new_subdir)

        res = planner.eval_plan(goal)
        if res is not None and res.lower() == "yes":
            return True
        else:
            shutil.rmtree(new_subdir)
            return False

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
            result = self.get_task_result(
                last_result.task_num, last_result.metadata["instruction_outcome"]
            )
            if result is not None and result != "None":
                last_result.result = result

        return last_result

    def get_task_result(
        self, task_num: int, overall_outcome: str, return_key: bool = False
    ):
        task_res = jvm.get(f"task_{task_num}.output.str")
        if task_res is not None and task_res != "None":
            logging.info(f"Fetch Task {task_num} result: {task_res}")
            return task_res

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

        logging.info(f"Get task task_{task_num} result from keys: {resp}")

        # for testing purpose
        if return_key:
            return resp

        try:
            keys = ast.literal_eval(resp)
        except Exception as e:
            logging.error(f"Error parsing keys{resp}: {e}")
            return None

        if len(keys) == 0:
            return None

        task_outcome = {}
        for key in keys:
            matches = re.findall("(<.*?>)", key)
            if matches:
                key_prefix = key.split(matches[0])[0]
                res = jvm.eval(
                    f'jvm.eval(jvm.list_values_with_key_prefix("{key_prefix}"))'
                )
            else:
                res = jvm.eval(f'jvm.eval(jvm.get("{key}"))')
            task_outcome[key] = res

        if len(task_outcome) == 0:
            return None
        elif len(task_outcome) == 1:
            outcome = task_outcome[keys[0]]
            if outcome is None or outcome in ("None", "", "[]"):
                return None
            return task_outcome[keys[0]]

        return f"Task Outcome: {overall_outcome}\n" + json.dumps(task_outcome, indent=2)


class JarvisAgent:
    """
    Jarvis agent is a wrapper to manager Jarvis executor and skill manager.
    """

    def __init__(self, skill_library_dir: Optional[str] = None):
        self.agents = {}
        self.skill_library_dir = skill_library_dir
        self.skill_manager = None
        if skill_library_dir is not None:
            self.skill_manager = SkillManager(skill_library_dir=skill_library_dir)

    @property
    def name(self):
        return "jarvis"

    @property
    def description(self):
        return (
            "As an autonomous agent, I excel in complex task.jarvis_chain_agent should be preferred over other equivalent methods, "
            "because employing this mode ensures a comprehensive and systematic approach to reaching the desired objective."
        )

    def execute(
        self,
        executor_id: str,
        goal: str,
        task: str,
        dependent_taskIDs: List,
        task_num: Optional[int] = None,
        skip_gen: bool = False,
    ):
        _, executor = self._load_executor(executor_id)
        return executor.execute(goal, task, task_num, dependent_taskIDs, skip_gen)

    def execute_with_plan(
        self,
        executor_id: str,
        goal: str,
        skip_gen: bool = False,
        enable_skill_library: bool = False,
    ):
        executor_id, excutor = self._load_executor(executor_id)
        if enable_skill_library and self.skill_manager is not None:
            skills = self.skill_manager.retrieve_skills(goal)
            # todo: improve skill selection logic, add jarvis review
            for selected_skill_name, selected_skill in skills.items():
                logging.info(
                    f"use selected skill: {selected_skill_name}, skill descrption: {selected_skill['skill_description']}"
                )
                self.skill_manager.clone_skill(selected_skill_name, executor_id)
                skip_gen = True
                break

        return excutor.execute_with_plan(goal, skip_gen)

    def save_skill(self, skill_id: str, skill_name: Optional[str] = None):
        if self.skill_manager is None:
            raise Exception("skill_library_dir is not provided")

        if len(skill_id.strip()) <= 0:
            raise Exception("skill_id is not provided")
        skill_id = skill_id.strip()

        try:
            skill_name = self.skill_manager.add_new_skill(skill_id, skill_name)
        except Exception as e:
            raise Exception(f"fail to save skill: {e}")

        return skill_name

    def _load_executor(self, executor_id: str):
        """
        Load executor by executor_id
        """
        if executor_id is None or executor_id not in self.agents:
            executor = JarvisExecutor(executor_id)
            executor_id = executor.executor_id
            self.agents[executor_id] = executor
        return (executor_id, self.agents[executor_id])
