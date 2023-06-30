from typing import Optional
from dotenv import load_dotenv
import time, logging
import json

from smartgpt import gpt
from smartgpt import translator

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
- Fetch: Retrieves content from a URL and saves it to the database.
- TextCompletion: Generates human-like text. When 'prompt' refers to previous outputs or data, use @eval(jvm.get('key')) to reference the data explicitly.
- Loop: Repeats instructions for a specific number of iterations.
- If: Provides conditional control in tasks.
- Set: Stores a value in the database. The value can be a string, a list, or an integer.
- ToolAgent: Calls an very smart agent to select the best tool to process the task. It will always return higher quality results.  It is especially useful when the task is complex and cannot be efficiently completed with a single instruction or even a combination of other instructions. If other instructions seem inefficient or inadequate to fulfill the task, consider the 'ToolAgent'. The agent will return a result in the format defined format, allowing subsequent instructions to continue processing the task.


Your responses should be in standard JSON format and include: {goal, main_task_objective, task_list, task_dependency, reasoning_for_each_task, hints_from_user (if any)}. An example is as follows:

{
  "goal": "Compose a blog post introducing TiDB Serverless in markdown format, ensuring all sections are linked in an index file.",
  "main_task_objective": "To create a detailed and informative blog post about TiDB Serverless, outlining its key points and features in an engaging manner.",
  "task_list": [
    {
      "task_num": 1,
      "task": "Store the links 'https://me.0xffff.me/dbaas1.html', 'https://me.0xffff.me/dbaas2.html' in database",
      "objective": "To ensure the source links are accessible to the following tasks.",
      "tools": ["Set"],
      "outcome": "The key 'source_links' in the database now contains the required links."
    },
    {
      "task_num": 2,
      "task": "Retrieve links from database(ref outcome), then loop through each link, fetch the content, and take notes on the key points and features of TiDB Serverless",
      "objective": "To gather necessary information and understand the fundamental aspects of TiDB Serverless from the provided links.",
      "tools": ["Loop", "Fetch", "TextCompletion"],
      "outcome": "A list of notes highlighting the key points and features of TiDB Serverless is available."
    },
    // Additional tasks...
  ],
  "reasoning_for_each_task": ["explaining how each task leverages other tasks's outcomes"],
  "task_dependency": {
    "2": [1],
    "3": [2],
  },
  "hints_from_user": ["Any additional instructions or information provided by the user, which can guide the task generation process"]
}


"""


def gen_instructions(model: str, replan: bool = False):
    if replan:
        logging.info("Replanning...")
        plan = gen_plan(model)
        plan = plan[plan.find("{") : plan.rfind("}") + 1]
        with open("plan.json", "w") as f:
            f.write(plan)
        exit(0)

    logging.info("Translating plan to instructions...")
    args = json.load(open("plan.json"))
    args.pop("reasoning_for_each_task", None)
    args.pop("tools_analysis_for_each_task", None)

    # Prepare task dependencies
    task_dependency = {int(k): [int(i) for i in v] for k, v in args.pop("task_dependency", {}).items()}
    task_outcome = {}

    # Filter and translate tasks
    args['task_list'] = [{k: v for k, v in task.items() if k in ['task_num', 'task', 'objective', 'outcome']} for task in args['task_list']]
    task_num_to_task = {task['task_num']: task['task'] for task in args['task_list']}
    start_seq = 1
    for task in args['task_list']:
        task_num = task['task_num']
        previous_outcome = [task_outcome[i] for i in task_dependency.get(task_num, [])]
        previous_tasks = {i: task_num_to_task[i] for i in task_dependency.get(task_num, [])}
        instrs = translator.translate_to_instructions({
            "first_task":task_num == 1,
            "goal":args["goal"],
            "task":task['task'],
            "objective":task['objective'],
            "previous_tasks":previous_tasks,
            "start_seq":start_seq,
            "previous_outcome":previous_outcome
        }, model=model)
        tmp = json.loads(instrs)
        start_seq = int(tmp['end_seq']) + 1
        task_outcome[task_num] = tmp['overall_outcome']
        with open(f"{task_num}.json", "w") as f:
            f.write(instrs)


def gen_plan(model: str):
    #input the goal
    goal = input("Please input your goal:\n")

    try:
        logging.info("========================")
        user_prompt = (
            f"give me a task list, our goal: {goal}\n\n"
            "your json response:```json"
        )

        resp = gpt.complete(prompt=user_prompt, model=model, system_prompt=GEN_PLAN__SYS_PROMPT)
        logging.info("Response from AI: %s", resp)
        return resp

    except Exception as err:
        logging.error("Error in main: %s", err)
        time.sleep(1)
