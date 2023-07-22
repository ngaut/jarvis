from typing import Dict, List
import yaml

from smartgpt.translator import Translator


class Compiler:
    def __init__(self, model: str):
        self.translator = Translator(model)

    def compile_plan(self) -> List[Dict]:
        with open('plan.yaml', 'r') as stream:
            plan = yaml.safe_load(stream)

        task_list = plan.get("task_list", [])
        task_dependency = plan.get("task_dependency", {})
        task_outcomes = {}
        result = []

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

            # Save the current task outcomes
            tmp = yaml.safe_load(instructions_yaml_str)
            result.append(tmp)
            task_outcomes[num] = {
                "task_num": num,
                "task": tmp['task'],
                "outcome": tmp['overall_outcome'],
            }

            with open(f"{num}.yaml", "w") as stream:
                stream.write(instructions_yaml_str)

        return result

    def compile_task(self, task_num):
        pass

    def compile_instruction(self, task_num, inst_seq):
        pass
