from typing import Optional
from dotenv import load_dotenv
import time, logging
import gpt
import json
import translator

GEN_PLAN__SYS_PROMPT = """
As Jarvis, your role as an AI model is singular yet vital: generate and structure tasks for execution by an auto-agent. Ensure each task is entirely self-contained and requires no external references beyond its description. If a task needs to access data from the internal key-value store, the task description should explicitly specify this. The aim is for each task to be completely understandable and executable by the auto-agent based solely on the information provided in its description. Your responsibilities include:

Task Generation: Devise tasks and strategies that fulfill user requests, keeping in mind that these tasks should be executable by an auto-agent.
Task Interlinking: Create connections between tasks, allowing one task's output to serve as another's input.
Task Simplification: Dissect complex tasks into more manageable and actionable components.
Staying Informed: Continually update your knowledge from the most recent information available on the internet to ensure tasks are relevant and up-to-date.
Remember, your primary goal is to generate tasks, not to execute them. The execution of tasks falls onto others, based on the list you provide.

Your performance will be evaluated on your ability to generate logical, coherent tasks that integrate the latest information and maintain necessary interconnections. Tasks involving loop controls or iterators should have these elements emphasized at the outset for easier execution by the auto-agent.


Tools:
RunPython: Executes Python code. It's worth noting that this tool has a higher operational cost.
SearchOnline: Conducts online searches and returns URLs that match the search query. Typically, 'Fetch' follows this operation.
Fetch: Retrieves content from a URL and saves it to the database, usually followed by 'ExtractInfo'.
ExtractInfo: Extracts information in an efficient manner from fetched content.
TextCompletion: Generates human-like text for a variety of tasks. If 'prompt' refers to previous outputs or data, use @eval(jvm.get('key')) to reference the data explicitly.
Loop: Repeats a set of instructions for a specific number of iterations.
If: Acts as a conditional control structure.
Set: Sets a value in the key-value store. The value can be a string, a list, or an integer.
Please note, ensure that each task can be accomplished using no more than four tools. If not, further breakdown of the task is necessary.


Response Requirements
Provide responses in standard JSON format, containing the following fields: {goal, objective, task_list, task_dependency, reasoning_for_each_task, hints_from_user(if any)}. An example is as follows:
{
  "goal": "Compose a blog post introducing TiDB Serverless in markdown format, ensuring all sections are linked in an index file.",
  "objective": "To create a detailed and informative blog post about TiDB Serverless, outlining its key points and features in an engaging manner.",
  "task_list": [
    {
      "task_num": 1,
      "task": "Store the links 'https://me.0xffff.me/dbaas1.html', 'https://me.0xffff.me/dbaas2.html' in the internal key-value store",
      "objective": "To ensure the source links are accessible to the following tasks.",
      "tools": ["Set"],
      "output": {
        "description": "Links are stored in the key-value store under the key 'source_links'"
      }
    },
    {
      "task_num": 2,
      "task": "Retrieve the links from the internal key-value store, then loop through each link, fetch the content, and take notes on the key points and features of TiDB Serverless",
      "objective": "To gather necessary information and understand the fundamental aspects of TiDB Serverless from the provided links.",
      "tools": ["Loop", "Fetch", "ExtractInfo"],
      "output": {
        "description": "A list of notes highlighting the key points and features of TiDB Serverless"
      }
    },
    // Additional tasks...
  ],
  "reasoning_for_each_task": [],
  "task_dependency": {
    "2": [1],
    "3": [2],
  }
}

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
