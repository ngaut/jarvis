import logging
import os
from typing import Dict, List

import yaml

from smartgpt.translator import Translator
from smartgpt.reviewer import Reviewer


class Compiler:
    def __init__(self, model: str):
        self.translator = Translator(model)
        self.reviewer = Reviewer(model)

    def load_yaml(self, file_name: str) -> Dict:
        try:
            with open(file_name, 'r') as stream:
                return yaml.safe_load(stream)
        except Exception as e:
            logging.error(f"Error loading file {file_name}: {e}")
            raise

    def write_yaml(self, file_name: str, data: str) -> None:
        try:
            with open(file_name, "w") as stream:
                stream.write(data)
        except Exception as e:
            logging.error(f"Error writing to file {file_name}: {e}")
            raise

    def create_task_info(self, task, num, deps, plan, previous_outcomes) -> Dict:
        return {
            "first_task": not deps,
            "task_num": num,
            "hints": plan.get("hints_from_user", []),
            "task": task['task'],
            "objective": task['objective'],
            "start_seq": 1000 * num + 1,
            "previous_outcomes": previous_outcomes
        }

    def check_diff(self, task_outcome, origin) -> bool:
        if origin is None:
            return True
        return task_outcome['overall_outcome'] != origin['overall_outcome']

    def compile_plan(self) -> List[Dict]:
        plan = self.load_yaml('plan.yaml')

        task_list = plan.get("task_list", [])
        task_dependency = plan.get("task_dependency", {})
        task_outcomes = {}
        result = []

        for task in task_list:
            num = task['task_num']
            deps = task_dependency.get(str(num), [])
            previous_outcomes = [task_outcomes[i] for i in deps]
            file_name = f"{num}.yaml"

            task_info = self.create_task_info(task, num, deps, plan, previous_outcomes)
            instructions_yaml_str = self.translator.translate_to_instructions(task_info)
            #self.reviewer.review_instructions_gen(num, self.translator.messages)
            self.write_yaml(file_name, instructions_yaml_str)
            task_outcome = yaml.safe_load(instructions_yaml_str)

            result.append(task_outcome)
            task_outcomes[num] = {
                "task_num": num,
                "task": task_outcome['task'],
                "outcome": task_outcome['overall_outcome'],
            }

        return result

    def recompile_task_in_plan(self, recompile_task_num) -> List[Dict]:
        plan = self.load_yaml('plan.yaml')

        task_list = plan.get("task_list", [])
        task_dependency = plan.get("task_dependency", {})
        task_outcomes = {}
        result = []
        need_to_recompile_subsequent_tasks = False

        for task in task_list:
            num = task['task_num']
            deps = task_dependency.get(str(num), [])
            previous_outcomes = [task_outcomes[i] for i in deps]
            file_name = f"{num}.yaml"

            task_info = self.create_task_info(task, num, deps, plan, previous_outcomes)

            task_outcome = None
            if num < recompile_task_num and os.path.exists(file_name):
                task_outcome = self.load_yaml(file_name)
            elif num > recompile_task_num and os.path.exists(file_name) and not need_to_recompile_subsequent_tasks:
                task_outcome = self.load_yaml(file_name)

            origin = self.load_yaml(file_name) if num == recompile_task_num and os.path.exists(file_name) else None

            if not task_outcome:
                instructions_yaml_str = self.translator.translate_to_instructions(task_info)
                #self.reviewer.review_instructions_gen(num, self.translator.messages)
                self.write_yaml(file_name, instructions_yaml_str)
                task_outcome = yaml.safe_load(instructions_yaml_str)

            if num == recompile_task_num:
                need_to_recompile_subsequent_tasks = self.check_diff(task_outcome, origin)

            result.append(task_outcome)
            task_outcomes[num] = {
                "task_num": num,
                "task": task_outcome['task'],
                "outcome": task_outcome['overall_outcome'],
            }

        return result
