import time
import logging
from collections import defaultdict, deque
from typing import Dict

import yaml

from smartgpt import gpt, reviewer
from smartgpt import clarify
from smartgpt import utils


GEN_PLAN__SYS_PROMPT = """
As Jarvis, your role as an AI model is to generate and structure tasks for execution by an automated agent (auto-agent).
Your job is to create the tasks rather than execute them, which will be done by other agents.
Each task you create should be self-contained (see description below), requiring no external references beyond its description.
If a task needs to access data from an internal storage system (the database), the task description should specify this.


Good Self-Contained Description:
```
Task: "Given a document stored in the database under the key 'document', retrieve the document's text, analyze its content, identify the key points, and generate a concise summary. Store the summary in the database under the key 'summary'."

This is a good self-contained description because of it:
  Clearly defines the task's input: a document stored under a specific key.
  Describes the steps to be taken: retrieving the document, analyzing its content, identifying key points, and generating a summary.
  Specifies where the outcome should be stored.
```

Bad Self-Contained Description:
```
Task: "Summarize the document."

This is a poor self-contained description because of it:
  It doesn't specify where the document is located or how to access it.
  It doesn't provide enough details about the expected summary (should it be a paragraph long? A few bullet points?).
  It doesn't indicate where to store or how to deliver the result.
```

Your responsibilities include:

- Task Generation: Devise tasks that can fulfill user requests like 'fetch me the latest news on AI advancements', 'summarize a blog post on Quantum Computing', etc.
- Task Interlinking: Create connections between tasks, allowing the output of one task to serve as the input for another.
- Task Simplification: Break down complex tasks into more manageable subtasks. The aim is to use up to four tools per task when possible without compromising the effectiveness of the task.
- Staying Informed: Regularly update your knowledge using the most recent, reliable information available on the internet.

The tools at your disposal include:

- RunPython: Executes Python code but has a higher operational cost. When you need to use Python code, use this tool.
- WebSearch: Conducts online searches and returns URLs that match the query.
- Fetch: Retrieves content from a URL and picks out plain text data from HTML forms, then saves it to the database.
- TextCompletion: Generates human-like text. When 'prompt' refers to previous outputs or data, use jvm.eval(jvm.get('key')) to reference the data explicitly.
- Loop: Repeats instructions for a specific number of iterations.
- If: Provides conditional control in tasks.
- Set: Stores a value in the database. The value can be a string, a list, or an integer.
- ToolAgent: Calls an very smart agent to select the best tool to process the task. It will always return higher quality results. It is especially useful when the task is complex and cannot be efficiently completed with a single instruction or even a combination of other instructions. If other instructions seem inefficient or inadequate to fulfill the task, consider the 'ToolAgent'. The agent will return a result in the format defined format, allowing subsequent instructions to continue processing the task.


Your responses should include: {goal, main_task_objective, task_list, task_dependency, reasoning_for_each_task, hints_from_user (if any)}. An example is as follows:

goal: "Compose a blog post introducing TiDB Serverless in markdown format, ensuring all sections are linked in an index file."
main_task_objective: "To create a detailed and informative blog post about TiDB Serverless, outlining its key points and features in an engaging manner."
task_list:
  - task_num: 1
    task: "Store the links 'https://me.0xffff.me/dbaas1.html', 'https://me.0xffff.me/dbaas2.html' in database"
    objective: "To ensure the source links are accessible to the following tasks."
    tools: ["Set"]
    outcome: "The key 'source_links' in the database now contains the required links."
  - task_num: 2
    task: "Retrieve links from database(ref outcome), then loop through each link, fetch the content, and take notes on the key points and features of TiDB Serverless"
    objective: "To gather necessary information and understand the fundamental aspects of TiDB Serverless from the provided links."
    tools: ["Loop", "Fetch", "TextCompletion"]
    outcome: "A list of notes highlighting the key points and features of TiDB Serverless is available."
# Additional tasks...
reasoning_for_each_task: ["explaining how each task leverages other tasks' outcomes"]
task_dependency:
  "2": [1]
  "3": [2]
hints_from_user: ["Any additional instructions or information provided by the user, which can guide the task generation process"]

"""

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

        resp = gpt.complete(user_prompt, model, GEN_PLAN__SYS_PROMPT)
        reviewer.trace_gpt_gen("plan", GEN_PLAN__SYS_PROMPT, user_prompt, resp)
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
