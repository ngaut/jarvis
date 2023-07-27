import time
import logging
from collections import defaultdict, deque
from typing import Dict

import yaml

from smartgpt import gpt
from smartgpt import clarify
from smartgpt import utils
from smartgpt import preprompts


def gen_plan(model: str, goal: str) -> Dict:
    if not goal:
        # input the goal
        input_goal = input("Please input your goal:\n")
        goal = clarify.clarify_and_summarize(input_goal)

    try:
        logging.info("========================")
        logging.info(f"The goal: {goal}")

        user_prompt = (
            f"The goal: \"\"\"\n{goal}\n\"\"\"\n\n"
            "Please generate the task list that can finish the goal.\n"
            "Your YAML response:```yaml\n"
        )

        resp = gpt.complete(user_prompt, model, preprompts.get("planner_sys_prompt"))
        # reviewer.Reviewer().review_plan_gen(resp)

        resp = sort_plan(utils.strip_yaml(resp))
        with open("plan.yaml", "w") as stream:
            stream.write(resp)

        return yaml.safe_load(resp)

    except Exception as err:
        logging.error("Error in main: %s", err)
        time.sleep(1)
        raise err


def sort_plan(plan_yaml_str: str) -> str:
    try:
        plan = yaml.safe_load(plan_yaml_str)
    except yaml.YAMLError as err:
        logging.error(f"Error loading plan file: {err}")
        raise

    task_list = plan.get("task_list", [])
    graph = plan.get("task_dependency", {})

    # Initialize a dictionary to hold the in-degree of all nodes
    in_degree = {task['task_num']: 0 for task in task_list}
    # Initialize a dictionary to hold the out edges of all nodes
    out_edges = defaultdict(list)

    # Calculate in-degrees and out edges for all nodes
    for task_id, dependencies in graph.items():
        task_id = int(task_id)  # convert to integer as in task_list it's integer
        for dependency in dependencies:
            out_edges[dependency].append(task_id)
            in_degree[task_id] += 1

    # Use a queue to hold all nodes with in-degree 0
    queue = deque([task_id for task_id in in_degree if in_degree[task_id] == 0])
    sorted_task_list = []

    # Perform the topological sort
    while queue:
        task_id = queue.popleft()
        sorted_task_list.append(task_id)

        for next_task in out_edges[task_id]:
            in_degree[next_task] -= 1
            if in_degree[next_task] == 0:
                queue.append(next_task)

    # Check if graph contains a cycle
    if len(sorted_task_list) != len(in_degree):
        logging.error("The plan cannot be sorted due to cyclic dependencies.")
        exit(-1)

    # Generate a map from old task IDs to new task IDs
    id_map = {old_id: new_id for new_id, old_id in enumerate(sorted_task_list, start=1)}

    # Update task IDs in the task list
    for task in task_list:
        task['task_num'] = id_map[task['task_num']]

    # Sort task list by task_num
    plan['task_list'] = sorted(task_list, key=lambda task: task['task_num'])

    # Update task IDs in the task dependency list
    new_task_dependency = {str(id_map[int(task_id)]): [id_map[dep] for dep in deps] for task_id, deps in graph.items()}
    plan['task_dependency'] = new_task_dependency

    # Dump the updated plan back to YAML
    sorted_plan_yaml_str = yaml.dump(plan)
    return sorted_plan_yaml_str
