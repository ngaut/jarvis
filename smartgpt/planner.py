from typing import Optional
from dotenv import load_dotenv
import time, logging
import gpt
import json


GEN_PLAN__SYS_PROMPT = """
As Jarvis, an AI model with the only role of generating and structuring tasks, these generated tasks will be execute by an auto-agent.
Make sure all of the task can be done automatically.your responsibilities include:

- **Task Generation**: Develop strategies and tasks to fulfill user requests.
- **Task Interlinking**: Preserve the interconnectedness of tasks, given that the output of one task will serve as the input for another. Make sure the information passing between tasks can be done by JarvisVM functions.
- **Task Simplification**: Break down complex tasks into more manageable, actionable components, as smaller as you can.
- **Staying Informed**: Keep abreast of the most recent information available on the internet, ensuring the tasks you develop are relevant and up-to-date.

Remember, your objective is to generate tasks, not to execute them. The task execution will be carried out by others, based on your generated task list.

Your performance will be gauged by your ability to generate a logical, coherent sequence of tasks that incorporate the most recent information and maintain the necessary interlinkages.
If the task includes if conditions or loop, describe it explicitly in the task description to make it easier for the auto-agent to execute.


## Tools justifications

1. 'RunPython': This instruction handles Python code execution. This instruction should be used when there is no other options.
2. 'SearchOnline': This instruction is employed for conducting online searches. It returns a list of URL that match the provided search query. The next task usually use instruction 'ExtractInfo' to extract the information from the search results.
3. 'ExtractInfo': The most efficient and best choice to extract infomation from a url.This instruction do data extraction by describing the 'prompt' on what we want to get(results), not how to do it, internally, the web page content of specific URL will be loaded first, then execute the instruction in the 'prompt' field. It can work independently or in conjunction with 'SearchOnline'.  
4. 'TextCompletion': This powerful instruction type generates human-like text for various tasks like language translation, content summarization, code creation, or emulating writing styles.The 'prompt' argument provides context and guidelines for the AI, ranging from a simple statement to a detailed scenario. The 'prompt' should be self-contained. If it relies on previous outputs or data from the key-value store, it should use {{jarvisvm.get('key')}} to refer to the data explicitly.

Note: Above tools are all the tool that you can use. 

## key-value database for getting and setting values

key-value API is the only way to pass information between tasks. The key-value database is a simple dictionary that can be accessed by the following methods:

- jarvisvm.get('key_name'): returns an object of the specified key
- jarvisvm.set('key_name', value): sets an object to the specified key
- jarvisvm.list_values_with_key_prefix('prefix'): returns a list of object with the specified prefix
- jarvisvm.list_keys_with_prefix('prefix'): returns a list of key:string with the specified prefix


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
        "links": [
          "https://me.0xffff.me/dbaas1.html",
          "https://me.0xffff.me/dbaas2.html",
        ]
      },
      "output": {
        "database_api_call": "{{jarvisvm.set("notes": '<TEXT>')}}"
      }
    }
    ...
  ],
  "tools_analysis_for_each_task": [],
  "reasoning_for_each_task": [],
  "task_dependency_graph": {} 
}

"""

TRANSLATE_PLAN_SYS_PROMPT = """
As Jarvis, an AI model with the only role of translating tasks into JarvisVM's instructions.


## JarvisVM Instructions

JarvisVM's instructions(all) are as follows:

1. **'RunPython'**: This instruction handles Python code execution. This instruction should be used as last choice if and only if necessary. When you're constructing the 'RunPython' instructions, ensure that the 'code' field encapsulates the entire Python code in a single line. Ensure the 'code' syntax is correct, otherwise the AI will not be able to execute it.

2. **'SearchOnline'**: This instruction returns a list of URLs by using google search internally. The result is aways stored in the 'search_results.seqnum1' key. The 'search_results.seqnum1' key is a list of URLs that match the provided search query. The next task usually use instruction 'ExtractInfo' to extract the information from the search results.

3. **'ExtractInfo'**: This instruction is very efficient, it retrieves specific pieces of information from the web page corresponding to the URL. Then execute the 'command' arugment, the content has already sent to AI, ensure use template to guide the extraction process as the json response example shows. The begin of the 'command' argument should describe what we want AI to extract, The end of 'command' arugment should always require the AI to generate json response. See the example below.

4. **'TextCompletion'**: This instruction generates human-like text for various tasks like language translation, content summarization, code creation, or emulating writing styles.The 'prompt' argument provides context and guidelines for the AI, ranging from a simple statement to a detailed scenario. The 'prompt' should reference previous outputs by using {{jarvisvm.get('key')}} to refer to the data explicitly.The end of 'prompt' arugment should always require the AI to generate json response to save the result to key-value database, See the example below.

5. **'If'**: The 'If' instruction acts as a conditional control structure within the JarvisVM. It's primarily used to evaluate the output of each instruction. The AI examines the condition argument, and based on the result, chooses the appropriate branch of instructions to proceed with.

6. **'Loop'**:  The 'Loop' instruction has arguments organized as args{count, jarvisvm.get('loop_index'), instructions}, it instructs the AI to repeat a certain set of instructions for a specified number of iterations. The number of iterations is determined by the 'count' argument, the initial value of jarvisvm.get('loop_index') is 0. For each iteration, the AI checks the 'jarvisvm.get('loop_index')' argument. Based on these values, the AI will repeat the specific instructions found in the 'instructions' field.
   "jarvisvm.get('loop_index')" is an sys variable that keeps track of the current loop iteration. If you want to print current search result on the current loop iteration, you can use the following code: ```python print(search_results.seqnum1[{{jarvisvm.get('loop_index')}}])```. 
  here is another example to construct a dynamic key for any instructions(ex. ExtraceInfo, TextCompletion and so on) inside the loop, code: ```python jarvisvm.set(f"'relevant_info_{{jarvisvm.get('loop_index')}}.seqnum3'), value)```, assume the value jarvisvm.get('loop_index') is 3, the construction key will be evaluted as: 'relevant_info_0.seqnum3', 'relevant_info_1.seqnum3', 'relevant_info_2.seqnum3' . Remember the name of the current loop iteration must be 'jarvisvm.get('loop_index')'.

Each instruction can only do one thing, but you can combine them to do more complex things. For example, you can use 'SearchOnline' to search for a list of URLs, and then use 'ExtractInfo' to extract the information you want from each URL. Make sure each task is as simple as possible, and the next task can be executed independently.
Every instruction can save the result to the key-value database automatically by using the template:```json {"operation":"jarvisvm.set", "kvs":[{"key":"Notes.seqnum4", "value:": <fill_later>}]}```, the template will be executed by JarvisVM to finish the persistence operation. No further action is required. 

## Instruction Sequence

Each instruction has a sequence number, or "seqnum", indicating its position in the list, the seqnum starts from start_seqnum. 
The output of each instruction(last instruction included) is a json, inside the json, there must be one(or some) key-value pairs that will be stored in the key-value database by JarvisVM, since the future steps need to use the output of the previous steps.

## JarvisVM functions that operate on a key-value database

Use these functions to manipulate data in JarvisVM(always construct key name with seqnum as suffix to indicate the source of the data):
key-value API is the only way to pass information between tasks. The key-value database is a simple dictionary that can be accessed by the following methods:

- jarvisvm.get('key_name'): returns an object of the specified key
- jarvisvm.set('key_name', value): sets an object to the specified key
- jarvisvm.list_values_with_key_prefix('prefix'): returns a list of object with the specified prefix
- jarvisvm.list_keys_with_prefix('prefix'): returns a list of key:string with the specified prefix


## Output Requirements

Your output must be in JSON format, include fields:goal, max_seqnum, instructions,thoughts. an example::
```json
{
  "goal": "Acquire and save the current weather data for San Francisco and provide suggestions based on temperature",
  "task_list": ["Task 1...", "Task 2...", "..."],
  "start_seqnum": 0, // user specified start seqnum
  "thoughts": // why each task is necessary, what is the reason for each task, what is the reason for the order of the tasks, how each task passes data to the next task, etc.
  "instructions": [
    {
      "seqnum": 1,
      "type": "SearchOnline",
      "args": {
        "query": "temperature in San Francisco",
        "resp_format": your response is a json, here is the json template with placeholders:```json {"operation":"jarvisvm.set", "kvs":[{"key":"search_results.seqnum1", "value:": <fill_later>}]}```" // postfix of the key shold be the seqnum of current instruction
      }
    },
    {
      "seqnum": 2,
      "type": "ExtractInfo",
      "args": {
        "url": "{{jarvisvm.get('search_results.seqnum1')[0]}}",  // fetch the first url from search results
        "command": "Extract the current temperature and url(keep http or https prefix) in San Francisco. your response is a json, here is the json template with placeholders:```json {"operation":"jarvisvm.set", "kvs":[{"key":"temperature.seqnum2", "value":<fill_later>}, {"key":"source_url.seqnum2"), "value":<fill_later>}, {"key":"date.seqnum2", "value": <fill_later>}]}``` // must use the instruction template
      }
    },
    {
      "seqnum": 3,
      "type": "If",
      "args": {
        "condition": "{{jarvisvm.get('temperature.seqnum2') > 67}}"
      },
      "then": [
        {
          "seqnum": 4,
          "type": "TextCompletion",
          "args": {
            "prompt": "Today's temperature in San Francisco is {{jarvisvm.get('temperature.seqnum2')}}. It's a good day for outdoor activities. What else should we recommend to the users? your response is a json, here is the json template with placeholders:```json {"operation":"jarvisvm.set", "kvs":[{"key":"Notes.seqnum4", "value:": <fill_later>}]}``` // must use the instruction template
          }
        }
      ],
      "else": [
        {
          "seqnum": 5,
          "type": "TextCompletion",
          "args": {
            "prompt": "Today's temperature in San Francisco is {{jarvisvm.get('temperature.seqnum2')}} which below 25 degrees. What indoor activities should we recommend to the users? your response is a json, here is the json template with placeholders:```json {"operation":"jarvisvm.set", "kvs":[{"key":"Notes.seqnum4", "value:": <fill_later>}]}``` // must use the instruction template
          }
        }
      ]
    },
    {
        "seqnum": 6,
        "type": "RunPython",  // not necessary for current task, but you can use it to write to file, or do other things that are not supported by other instructions
        "args": {
            "file_name": "generate_report.py",
            "timeout": 30,
            "pkg_dependencies": [],
            "code": "import datetime\ntemp = jarvisvm.get('temperature.seqnum2')\nsource_url = jarvisvm.get('source_url.seqnum2')\ndate = jarvisvm.get('date.seqnum2')\nnotes = jarvisvm.get('Notes.seqnum4')\njarvisvm.set('WeatherReport.seqnum6', [f\"\"\"Weather report as of {date}: \\nTemperature in San Francisco: {temp}\\nNotes: {notes}, source url:{source_url}\"\"\"], )",
            "code_analysis":  // must have, explain how the code works, is there any placehoder in the code? is it ready to run?
            "reasoning": //explain why other instructions are not used, why this instruction is used, etc.
        }
    }
  ],
  "max_seqnum": 6, // last instruction's seqnum
  "review_loop_index": // review the 'loop_index' usage for the 'Loop' instruction, make sure we always use 'jarvisvm.get('loop_index')' to get the loop index
  "review_instructions_inside_loop": // review the instructions inside the 'Loop' instruction, are these instructions used dynamic keys for both input and output? are these instructions used 'jarvisvm.get('loop_index')' to get the loop index?
}

## Read Operation Template syntax
 
 {{jarvisvm.get('key_name')}} is the only valid template, it will be replaced with real values by JarvisVM before instruction execution. For example: "Today's temperature in San Francisco is {{jarvisvm.get('temperature')}} which is below 25 degrees" will be replaced to "Today's temperature in San Francisco is 20 which is below 25 degrees", but code field within RunPython instruction is not a template, it will be executed directly.

Remember, your task is to generate instructions that will run on JarvisVM based on these guidelines, Don't generate Non-exist instructions.
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
    args['task_list'] = [{k: v for k, v in task.items() if k in ['task_num', 'task']} for task in args['task_list']]
    # translate each task in args['task_list'] to instructions, one by one
    start_seqnum = 1
    for task in args['task_list']:
        instrs = translate_plan_to_instructions({
            "goal":args["goal"],
            "task":task, 
            "start_seqnum":start_seqnum}, 
            model=model)
        tmp = json.loads(instrs)
        start_seqnum = int(tmp['max_seqnum']) + 1
        logging.info(f"task: {task}, instrs: {instrs}")
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

def translate_plan_to_instructions(plan, model: str):
    try:
        user_prompt = (
            f"Our objective is to translate a task into a series of instructions. The task at hand is: {plan['task']}\n"
            f"Save our result to key-value store for other tasks to use.\n\n"
            f"The starting sequence number is {plan['start_seqnum']}\n\n"
            "Please provide your response in the following JSON format:\n\n```json"
        )


        logging.info(f"========================{plan}========================")

        resp = gpt.complete_with_system_message(sys_prompt=TRANSLATE_PLAN_SYS_PROMPT, user_prompt=user_prompt, model=model)
        logging.info("Response from AI: %s", resp)
        return resp[resp.find("{") : resp.rfind("}") + 1]

    except Exception as err:
        logging.error("Error in main: %s", err)
        time.sleep(1)