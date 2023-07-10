from typing import Optional
import time
import logging
import yaml

from smartgpt import gpt
from smartgpt import translator
from smartgpt import clarify
from smartgpt import utils

GEN_PLAN__SYS_PROMPT = """
As Jarvis, your role as an AI model is to generate and structure tasks for execution by an automated agent (auto-agent).
Your job is to create the tasks, but not to execute them, which will be done by other agents.
Each task you create should be self-contained(see description bellow), requiring no external references beyond its description.
If a task needs to access data from an internal storage system (the database), the task description should specify this.


Good Self-Contained Description:
```
Task: "Given a document stored in the database under the key 'document', retrieve the document's text, analyze its content, identify the key points, and generate a concise summary. Store the summary in the database under the key 'summary'."

This is a good self-contained description because it:
  Clearly defines the task's input: a document stored under a specific key.
  Describes the steps to be taken: retrieving the document, analyzing its content, identifying key points, and generating a summary.
  Specifies where the outcome should be stored.
```

Bad Self-Contained Description:
```
Task: "Summarize the document."

This is a poor self-contained description because it:
  Doesn't specify where the document is located or how to access it.
  Doesn't provide enough details about the expected summary (should it be a paragraph long? A few bullet points?).
  Doesn't indicate where to store or how to deliver the result.
```

Your responsibilities include:

- Task Generation: Devise tasks that can fulfill user requests like 'fetch me the latest news on AI advancements', 'summarize a blog post on Quantum Computing', etc.
- Task Interlinking: Create connections between tasks, allowing the output of one task to serve as the input for another.
- Task Simplification: Break down complex tasks into more manageable subtasks. The aim is to use no more than four tools per task when possible without compromising the effectiveness of the task.
- Staying Informed: Regularly update your knowledge using the most recent, reliable information available on the internet.

The tools at your disposal include:

- RunPython: Executes Python code but has a higher operational cost, when you need to use Python code, use this tool.
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
reasoning_for_each_task: ["explaining how each task leverages other tasks's outcomes"]
task_dependency:
  "2": [1]
  "3": [2]
hints_from_user: ["Any additional instructions or information provided by the user, which can guide the task generation process"]


"""

def gen_instructions(model: str, replan: bool = False, goal: Optional[str] = None) -> int:
    if replan:
        logging.info("Replanning...")
        plan = utils.strip_yaml(gen_plan(model, goal))
        with open("plan.yaml", "w") as f:
            f.write(plan)
        return 0

    with open("plan.yaml", 'r') as file:
        args = yaml.safe_load(file)
        logging.debug(f"Loaded plan: {args}")

    args.pop("reasoning_for_each_task", None)

    # Prepare task dependencies
    task_dependency = {int(k): [int(i) for i in v] for k, v in args.pop("task_dependency", {}).items()}
    task_outcomes = {}

    # Filter and translate tasks
    args['task_list'] = [{k: v for k, v in task.items() if k in ['task_num', 'task', 'objective', 'outcome']} for task in args['task_list']]
    start_seq = 1
    for task in args['task_list']:
        task_num = task['task_num']
        previous_outcomes = [task_outcomes[i] for i in task_dependency.get(task_num, [])]
        instrs = translator.translate_to_instructions({
            "first_task": task_num == 1,
            "goal": args["goal"],
            "task": task['task'],
            "objective": task['objective'],
            "start_seq": start_seq,
            "previous_outcomes": previous_outcomes
        }, model=model)

        if instrs is not None:
          tmp = yaml.safe_load(instrs)
          start_seq = int(tmp['end_seq']) + 1
          task_outcomes[task_num] = {
              "task_num": task_num,
              "task": tmp['task'],
              "outcome": tmp['overall_outcome'],
          }
          with open(f"{task_num}.yaml", "w") as f:
              f.write(instrs)

        time.sleep(60)

    return len(args['task_list'])

def gen_plan(model: str, goal: Optional[str] = None) -> str:
    if goal is None:
      #input the goal
      input_goal = input("Please input your goal:\n")
      goal = clarify.clarify_and_summarize(input_goal)

    try:
        logging.info("========================")
        logging.info(f"The goal: {goal}")

        user_prompt = (
            f"The goal: {goal}.\n"
            "Please generate the task list that can finish the goal.\n"
            "Your YAML response:```yaml\n"
        )

        resp = utils.strip_yaml(gpt.complete(user_prompt, model, GEN_PLAN__SYS_PROMPT))
        logging.info("Response from AI: %s", resp)
        return resp

    except Exception as err:
        logging.error("Error in main: %s", err)
        time.sleep(1)
        raise err
