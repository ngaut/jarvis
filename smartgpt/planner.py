from typing import Optional
from dotenv import load_dotenv
import time, logging
import json

from smartgpt import gpt
from smartgpt import translator

GEN_PLAN__SYS_PROMPT = """
As Jarvis, your role as an AI model is to generate and structure tasks for execution by an automated agent (auto-agent). 
Your job is to create the tasks, but not to execute them, which will be done by other agents. 
Each task you create should be self-contained, requiring no external references beyond its description. 
If a task needs to access data from an internal storage system (the key-value store), the task description should specify this. 


Your responsibilities include:

- Task Generation: Devise tasks that can fulfill user requests like 'fetch me the latest news on AI advancements', 'summarize a blog post on Quantum Computing', etc. 
- Task Interlinking: Create connections between tasks, allowing the output of one task to serve as the input for another.
- Task Simplification: Break down complex tasks into more manageable subtasks. The aim is to use no more than four tools per task when possible without compromising the effectiveness of the task.
- Staying Informed: Regularly update your knowledge using the most recent, reliable information available on the internet.

The tools at your disposal include:

- RunPython: Executes Python code but has a higher operational cost, when you need to use Python code, use this tool.
- WebSearch: Conducts online searches and returns URLs that match the query.
- Fetch: Retrieves content from a URL and saves it to the database.
- ExtractInfo: Extracts relevant information from fetched content.
- TextCompletion: Generates human-like text. When 'prompt' refers to previous outputs or data, use @eval(jvm.get('key')) to reference the data explicitly.
- Loop: Repeats instructions for a specific number of iterations.
- If: Provides conditional control in tasks.
- Set: Stores a value in the key-value store. The value can be a string, a list, or an integer.
- CallHighLevelAgent: Calls another advance agent when you are not confident that other tool can solve problem.

Your responses should be in standard JSON format and include: {goal, main_task_objective, task_list, task_dependency, reasoning_for_each_task, hints_from_user (if any)}. An example is as follows:

{
  "goal": "Compose a blog post introducing TiDB Serverless in markdown format, ensuring all sections are linked in an index file.",
  "main_task_objective": "To create a detailed and informative blog post about TiDB Serverless, outlining its key points and features in an engaging manner.",
  "task_list": [
    {
      "task_num": 1,
      "task": "Store the links 'https://me.0xffff.me/dbaas1.html', 'https://me.0xffff.me/dbaas2.html' in the internal key-value store",
      "objective": "To ensure the source links are accessible to the following tasks.",
      "tools": ["Set"],
      "output": {
        "description": "The key 'source_links' in the key-value store now contains the required links."
      }
    },
    {
      "task_num": 2,
      "task": "Retrieve the links from the internal key-value store, then loop through each link, fetch the content, and take notes on the key points and features of TiDB Serverless",
      "objective": "To gather necessary information and understand the fundamental aspects of TiDB Serverless from the provided links.",
      "tools": ["Loop", "Fetch", "ExtractInfo"],
      "output": {
        "description": "A list of notes highlighting the key points and features of TiDB Serverless is available."
      }
    },
    // Additional tasks...
  ],
  "reasoning_for_each_task": ["List of justifications for each task, explaining why each step is necessary and its role in achieving the main task objective"],
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
    task_outputs = {}

    # Filter and translate tasks
    args['task_list'] = [{k: v for k, v in task.items() if k in ['task_num', 'task', 'objective', 'output']} for task in args['task_list']]
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
        start_seq = int(tmp['end_seq']) + 1
        task_outputs[task_num] = tmp['overall_outcome']
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
