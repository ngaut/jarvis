from typing import Optional
from dotenv import load_dotenv
import time, logging
import gpt
import json
import translator

GEN_PLAN__SYS_PROMPT = """
As Jarvis, an AI model with the only role of generating and structuring tasks, these generated tasks will be execute by an auto-agent.
Make sure all of the task can be done automatically.your responsibilities include:

- **Task Generation**: Develop strategies and tasks to fulfill user requests.
- **Task Interlinking**: Preserve the interconnectedness of tasks, given that the output of one task will serve as the input for another. Make sure the information passing between tasks can be done by JVM functions.
- **Task Simplification**: Break down complex tasks into more manageable, actionable components, as smaller as you can.
- **Staying Informed**: Keep abreast of the most recent information available on the internet, ensuring the tasks you develop are relevant and up-to-date.

Remember, your objective is to generate tasks, not to execute them. The task execution will be carried out by others, based on your generated task list.

Your performance will be gauged by your ability to generate a logical, coherent sequence of tasks that incorporate the most recent information and maintain the necessary interlinkages.

Please pay particular attention to tasks that include loop control or iterators. These tasks should be described explicitly at the beginning of the task description to make it easier for the auto-agent to execute later. For example, if a task involves iterating over a list, describe it like "loop through the list...".


## Tools justifications

- 'RunPython': This instruction handles Python code execution. This instruction is more expensive.
- 'SearchOnline': This instruction is employed for conducting online searches. It returns a list of URL that match the provided search query. Usually, the next task is instruction 'Fetch' to fetch the content from a url.
- 'Fetch': This instruction fetches the content of a URL. Save the content to database. The next task usually use instruction 'ExtractInfo' to extract the information from the content.
- 'ExtractInfo': The most efficient and best choice to extract infomation. 
- 'TextCompletion': This powerful instruction type generates human-like text for various tasks like language translation, content summarization, code creation, or emulating writing styles.The 'prompt' argument provides context and guidelines for the AI, ranging from a simple statement to a detailed scenario. The 'prompt' should be self-contained. If it relies on previous outputs or data from the key-value store, it should use @eval(jvm.get('key')}} to refer to the data explicitly.
- 'Loop': This instruction is used to repeat a certain set of instructions for a specified number of iterations
- 'If': The 'If' instruction acts as a conditional control structure
Note: Above tools are all the tool that you can use. 


## Response Requirements

Your response should be structured in a standard JSON format, it includes fields: {goal,task_list, task_dependency, reasoning_for_each_task, hints_from_user(if exist),  bellow is an response example that demonstrates the structure of the response, and how to use the tools:
{
  "goal": "Write a blog post introducing TiDB Serverless using markdown format and linking all the sections in an index file.",
  "objective": "Create an informative and comprehensive blog post about TiDB Serverless by studying relevant resources, outlining key points and features, and crafting content in an engaging manner.",
  "hints_from_user": "Please study the content of these links first: https://me.0xffff.me/dbaas1.html, https://me.0xffff.me/dbaas2.html",
  "task_list": [
    {
      "task_num": 1,
      "task": "Loop through the provided links, read the content, and take notes on the key points and features of TiDB Serverless", 
      "objective": "To gather necessary information and understand the fundamental aspects of TiDB Serverless from the provided links.",
      "input": {
        "description": "",
        "links": [
          "https://me.0xffff.me/dbaas1.html",
          "https://me.0xffff.me/dbaas2.html"
        ]
      },
      "tools": ["Loop", "Fetch", "ExtractInfo", "TextCompletion"],
      "output": {
        "description": "Notes highlighting the key points and features of TiDB Serverless"
      }
    },
    {
      "task_num": 2,
      "task": "...",
      "objective": "...",
      "input": {},
      "tools": [],
      "output": {}
    },
    ...
  ],
  "reasoning_for_each_task": [],
  "task_dependency": [
    {
      "2": [1]
    },
    ...
  ]
}


"""


"""
    "task_dependency": [
    {"2": [1]},
    {"3": [1]},
    {"4": [1]},
    {"5": [1]},
    {"6": [1]},
    {"7": [1]},
    {"8": [2, 3, 4, 5, 6, 7]}
  ],
"""

def gen_instructions(model: str, replan: bool = False):
    if replan:
        logging.info("Replanning...")
        plan = gen_plan(model)
        plan = plan[plan.find("{") : plan.rfind("}") + 1]
        with open("plan.json", "w") as f:
            f.write(plan)

    logging.info("Translating plan to instructions...")
    args = json.load(open("plan.json"))
    args.pop("reasoning_for_each_task", None)
    args.pop("tools_analysis_for_each_task", None)
    
    # Prepare task dependencies
    task_dependency = {int(k): v for item in args.pop("task_dependency", []) for k, v in item.items()}
    task_outputs = {}

    # Filter and translate tasks
    args['task_list'] = [{k: v for k, v in task.items() if k in ['task_num', 'task', 'objective', 'input', 'output']} for task in args['task_list']]
    task_num_to_task = {task['task_num']: task['task'] for task in args['task_list']}
    start_seq = 1
    for task in args['task_list']:
        task_num = task['task_num']
        previous_outcome = [task_outputs[i] for i in task_dependency.get(task_num, [])]
        previous_tasks = {i: task_num_to_task[i] for i in task_dependency.get(task_num, [])}
        instrs = translator.translate_to_instructions({
            "goal":args["goal"],
            "task":task['task'], 
            "objective":task['objective'],
            "previous_tasks":previous_tasks,
            "start_seq":start_seq, 
            "previous_outcome":previous_outcome
        }, model=model)
        tmp = json.loads(instrs)
        start_seq = int(tmp['max_seq']) + 1
        task_outputs[task_num] = tmp['over_all_outcome']
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
        resp = gpt.complete_with_system_message(sys_prompt=GEN_PLAN__SYS_PROMPT, user_prompt=user_prompt, model=model)
        logging.info("Response from AI: %s", resp)
        return resp

    except Exception as err:
        logging.error("Error in main: %s", err)
        time.sleep(1)
