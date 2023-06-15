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
- **Task Interlinking**: Preserve the interconnectedness of tasks, given that the output of one task will serve as the input for another. Make sure the information passing between tasks can be done by JarvisVM functions.
- **Task Simplification**: Break down complex tasks into more manageable, actionable components, as smaller as you can.
- **Staying Informed**: Keep abreast of the most recent information available on the internet, ensuring the tasks you develop are relevant and up-to-date.

Remember, your objective is to generate tasks, not to execute them. The task execution will be carried out by others, based on your generated task list.

Your performance will be gauged by your ability to generate a logical, coherent sequence of tasks that incorporate the most recent information and maintain the necessary interlinkages.
If the task includes if conditions or loop, describe it explicitly in the beginning of the task description to make it easier for the auto-agent to execute later.


## Tools justifications

1. 'RunPython': This instruction handles Python code execution. This instruction should be used when there is no other options.
2. 'SearchOnline': This instruction is employed for conducting online searches. It returns a list of URL that match the provided search query. The next task usually use instruction 'ExtractInfo' to extract the information from the search results.
3. 'ExtractInfo': The most efficient and best choice to extract infomation from a url.This instruction do data extraction by describing the 'prompt' on what we want to get(results), not how to do it, internally, the web page content of specific URL will be loaded first, then execute the instruction in the 'prompt' field. It can work independently or in conjunction with 'SearchOnline'.  
4. 'TextCompletion': This powerful instruction type generates human-like text for various tasks like language translation, content summarization, code creation, or emulating writing styles.The 'prompt' argument provides context and guidelines for the AI, ranging from a simple statement to a detailed scenario. The 'prompt' should be self-contained. If it relies on previous outputs or data from the key-value store, it should use @eval_and_replace{{jarvisvm.get('key')}} to refer to the data explicitly.

Note: Above tools are all the tool that you can use. 


## Response Requirements

Your response should be structured in a standard JSON format, bellow is an response example that demonstrates the structure of the response, and how to use the tools:
{
  {
  "goal": "Write a blog post introducing TiDB Serverless using markdown format and linking all the sections in an index file.",
  "hints_from_user": "study the content of these links first: https://me.0xffff.me/dbaas1.html, https://me.0xffff.me/dbaas2.html",
  "task_list": [
    {
      "task_num":1,
      "task": "Loop through the provided links, read the content, and take notes on the key points and features of TiDB Serverless",
      "input": {
        "description": 
        "links": [
          "https://me.0xffff.me/dbaas1.html",
          "https://me.0xffff.me/dbaas2.html",
        ]
      },
      "tools": ["ExtractInfo", "TextCompletion"],
      "output": {
        "description": "notes on the key points and features of TiDB Serverless"
      }
    }
    ...
  ],
  "reasoning_for_each_task": [],
  "task_dependency_graph": {} 
}

"""


def gen_instructions(model: str, replan: bool = False):
    if replan:
        logging.info("Replanning...")
        plan = gen_plan(model)
        # strip the response to keep everything between '{' and '}'
        plan = plan[plan.find("{") : plan.rfind("}") + 1]
        # save plan to file
        with open("plan.json", "w") as f:
            f.write(plan)

    # translate plan to instructions  
    logging.info("Translating plan to instructions...")
    args = json.load(open("plan.json"))
    # remove reasoning_for_each_task from args
    args.pop("reasoning_for_each_task", None)
    args.pop("tools_analysis_for_each_task", None)
    args.pop("task_dependency_graph", None)
    # filter fields for each task in args['task_list'], only keep fields in the set ['task_num', 'task', 'input', 'output']
    # update args['task_list'] with the filtered task list
    args['task_list'] = [{k: v for k, v in task.items() if k in ['task_num', 'task', 'input', 'output']} for task in args['task_list']]
    # translate each task in args['task_list'] to instructions, one by one
    start_seqnum = 1
    previous_outcome = []
    previous_tasks = []
    for task in args['task_list']:
        instrs = translator.translate_to_instructions({
            "goal":args["goal"],
            "task":task['task'], 
            "previous_tasks":previous_tasks,
            "start_seqnum":start_seqnum, 
            "previous_outcome":previous_outcome
        },model=model)
        tmp = json.loads(instrs)
        start_seqnum = int(tmp['max_seqnum']) + 1
        # append to previous_outcome
        previous_outcome.append(tmp['over_all_outcome'])
        previous_tasks.append(task['task'])
        #logging.info(f"task: {task}, instrs: {instrs}")
        # save to file
        with open(f"{task['task_num']}.json", "w") as f:
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
