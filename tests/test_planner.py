import unittest

import yaml

from jarvis.smartgpt import planner


class TestPlaner(unittest.TestCase):
    def setUp(self):
        self.plan_yaml_str = """
task_list:
  - task_num: 1
    task: "abc"
    objective: ""
    tools: ["RunPython"]
    outcome: ""
  - task_num: 2
    task: "def"
    objective: ""
    tools: ["RunPython"]
    outcome: ""
  - task_num: 3
    task: "ghi"
    objective: ""
    tools: ["RunPython"]
    outcome: ""
  - task_num: 4
    task: "jkl"
    objective: ""
    tools: ["RunPython"]
    outcome: ""
task_dependency:
  "1": [2]
  "3": [2]
  "4": [3, 1]
"""

    def test_sort_plan(self):
        sorted_plan_yaml_str = planner.reorder_tasks(self.plan_yaml_str)
        sorted_plan = yaml.safe_load(sorted_plan_yaml_str)

        # Test if the tasks are sorted correctly
        expected_task_order = ["def", "abc", "ghi", "jkl"]
        sorted_task_order = [task['task'] for task in sorted_plan['task_list']]
        self.assertEqual(expected_task_order, sorted_task_order)

        # Test if the dependencies are updated correctly
        expected_dependency = {"2": [1], "3": [1], "4": [3, 2]}
        self.assertEqual(expected_dependency, sorted_plan['task_dependency'])


if __name__ == '__main__':
    unittest.main()
