import logging
import os
from typing import Dict, List, Optional

import yaml

from jarvis.smartgpt.translator import Translator


class Compiler:
    def __init__(self, translator_model: str):
        self.translator = Translator(translator_model)

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

    def create_task_info(self, task, objective, num, hints, previous_outcomes, goal) -> Dict:
        return {
            "first_task": num == 1,
            "task_num": num,
            "hints": hints,
            "task": task,
            "objective": objective,
            "start_seq": (num - 1 << 4) + 1,
            "previous_outcomes": previous_outcomes,
            "goal": goal
        }

    def check_outcome_changed(self, task_outcome, origin) -> bool:
        return task_outcome['overall_outcome'] != origin['overall_outcome']

    def compile_plan(self) -> List[Dict]:
        plan = self.load_yaml('plan.yaml')
        hints = plan.get("hints_from_user", [])
        goal = plan.get("goal", "")
        task_list = plan.get("task_list", [])
        task_dependency = plan.get("task_dependency", {})

        task_outcomes = {}
        result = []

        for task in task_list:
            num = task['task_num']
            deps = task_dependency.get(str(num), [])
            previous_outcomes = [task_outcomes[i] for i in deps]

            task_info = self.create_task_info(task['task'], task['objective'], num, hints, previous_outcomes, goal)
            instructions_yaml_str = self.translator.translate_to_instructions(task_info)

            self.write_yaml(f"{num}.yaml", instructions_yaml_str)

            task_instrs = yaml.safe_load(instructions_yaml_str)
            result.append(task_instrs)

            task_outcomes[num] = {
                "task_num": num,
                "task": task_instrs['task'],
                "outcome": task_instrs['overall_outcome'],
            }

        return result

    def compile_task_in_plan(self, specified_task_num: int) -> List[Dict]:
        plan = self.load_yaml('plan.yaml')
        hints = plan.get("hints_from_user", [])
        goal = plan.get("goal", "")
        task_list = plan.get("task_list", [])
        task_dependency = plan.get("task_dependency", {})

        task_outcomes = {}
        result = []
        recompile_subsequent_tasks = False

        for task in task_list:
            num = task['task_num']
            deps = task_dependency.get(str(num), [])
            previous_outcomes = [task_outcomes[i] for i in deps]
            file_name = f"{num}.yaml"

            origin = self.load_yaml(file_name) if os.path.exists(file_name) else None

            task_instrs = None
            if num < specified_task_num and os.path.exists(file_name):
                task_instrs = self.load_yaml(file_name)
            elif num > specified_task_num and os.path.exists(file_name) and not recompile_subsequent_tasks:
                task_instrs = self.load_yaml(file_name)

            if not task_instrs:
                task_info = self.create_task_info(task['task'], task['objective'], num, hints, previous_outcomes, goal)
                instructions_yaml_str = self.translator.translate_to_instructions(task_info)
                self.write_yaml(file_name, instructions_yaml_str)
                task_instrs = yaml.safe_load(instructions_yaml_str)

            result.append(task_instrs)

            task_outcomes[num] = {
                "task_num": num,
                "task": task_instrs['task'],
                "outcome": task_instrs['overall_outcome'],
            }

            if num == specified_task_num:
                recompile_subsequent_tasks = self.check_outcome_changed(task_instrs, origin) if origin else True

        return result

    def compile_task(self, task_num: int, task: str, goal: str, previous_outcomes: List, hints: Optional[List]=[], objective: Optional[str]="") -> Dict:
        task_info = self.create_task_info(task, objective, task_num, hints, previous_outcomes, goal)
        instructions_yaml_str = self.translator.translate_to_instructions(task_info)
        self.write_yaml(f"{task_num}.yaml", instructions_yaml_str)
        result = yaml.safe_load(instructions_yaml_str)
        return result
