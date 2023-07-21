import logging
import yaml

from smartgpt import translator


class Compiler:
    def __init__(self, model: str):
        self.translator = translator.Translator(model)

    def compile_plan(self):
        with open('plan.yaml', 'r') as stream:
            try:
                plan = yaml.safe_load(stream)
            except yaml.YAMLError as err:
                logging.error(f"Error loading plan file: {err}")
                raise

        task_list = plan.get("task_list", [])
        task_dependency = plan.get("task_dependency", {})
        task_outcomes = {}

        for task in task_list:
            num = task['task_num']
            deps = task_dependency.get(str(num), [])
            previous_outcomes = [task_outcomes[i] for i in deps]

            task_info = {
                "first_task": not deps,
                "task_num": num,
                "hints": plan.get("hints_from_user", []),
                "task": task['task'],
                "objective": task['objective'],
                "start_seq": 1000 * num + 1,
                "previous_outcomes": previous_outcomes
            }

            instructions_yaml_str = self.translator.translate(task_info)

            tmp = yaml.safe_load(instructions_yaml_str)
            task_outcomes[num] = {
                "task_num": num,
                "task": tmp['task'],
                "outcome": tmp['overall_outcome'],
            }

            with open(f"{num}.yaml", "w") as f:
                f.write(instructions_yaml_str)

    def compile_task(self, task_num):
        pass

    def compile_instruction(self, task_num, inst_seq):
        pass

