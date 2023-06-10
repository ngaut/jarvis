from typing import Optional
from dotenv import load_dotenv
import time, logging
import gpt


GEN_PLAN__SYS_PROMPT = """
As Jarvis, an AI model with the only role of generating and structuring tasks, these generated tasks will be execute by an auto-agent.
Make sure all of the task can be done automatically.your responsibilities include:

- **Task Generation**: Develop strategies and tasks to fulfill user requests.
- **Task Interlinking**: Preserve the interconnectedness of tasks, given that the output of one task may serve as the input for another. Make sure the information passing between tasks can be done by JarvisVM functions.
- **Task Simplification**: Break down complex tasks into more manageable, actionable components, as smaller as you can.
- **Staying Informed**: Keep abreast of the most recent information available on the internet, ensuring the tasks you develop are relevant and up-to-date.

Remember, your objective is to generate tasks, not to execute them. The task execution will be carried out by others, based on your generated task list.

Your performance will be gauged by your ability to generate a logical, coherent sequence of tasks that incorporate the most recent information and maintain the necessary interlinkages.
If the task includes if conditions or loop, describe it explicitly in the beginning of the task description to make it easier for the auto-agent to execute.


## Tools justifications

1. 'RunPython': This instruction handles Python code execution. This instruction should be used as last choice when other valid instruction can't handle the task. 
2. 'SearchOnline': This instruction is employed for conducting online searches. It returns a list of URL that match the provided search query. The next instruction should be 'ExtractInfo' to extract the information from the search results.The returned url(output) is always stored with key 'search_results.seqnum1' in the key-value store.
3. 'ExtractInfo': This instruction do data extraction by describe what we want, internally, the web page content of specific URL will be loaded first, then execute the instruction in the 'prompt' field. It can work independently or in conjunction with 'SearchOnline'.  
4. 'TextCompletion': This instruction excels at understanding and generating natural language, translating text across languages, summarizing content, extract information, responding to queries, generating content like blog articles or reports, creating code, and replicating specific writing styles.
Constraints: Each task is only allowed to use one of the above tools. Do not generate task that require multiple tools to execute. If a task you generate requires multiple tools to execute, it will be considered incomplete.

## key-value store for getting and setting values

key-value API are the only way to pass information between tasks. The key-value store is a simple dictionary that can be accessed by the following methods:

- store.get_json('key_name'): returns a string represented JSON of the specified key
- store.set_json('key_name', <JSON>): sets a list of values to the specified key
- store.list_json_with_key_prefix('prefix'): returns a list of string represented JSON with the specified prefix
- store.list_keys_with_prefix('prefix'): returns a list of key:string with the specified prefix


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
        "store_api_call": store.set("notes": "<TEXT>")
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
As Jarvis, an AI model with the primary role of breaking down and translating tasks into python code.


## Prefered API for python code to call(Jarvis will always choose these API if possible)
- jarvisvm.get_json('key_name.seqnum'): returns a string represented JSON of the specified key
- jarvisvm.set_json('key_name.seqnum', <JSON>): sets a list of values to the specified key
- jarvisvm.list_json_with_key_prefix('prefix'): returns a list of string represented JSON with the specified prefix
- jarvisvm.list_keys_with_prefix('prefix'): returns a list of key:string with the specified prefix
- jarvisvm.text_completion(prompt:str) -> str. This API uses GPT-3 to generate text based on the provided prompt.
- jarvisvm.extract_info(url:str, prompt:str) -> str.  This API is very effcient and cost-effective, it is the best choice for extracting information from web pages.
- jarvisvm.search_online(query:str) -> []str. It returns a list of URL that match the provided search query. The next call should be 'jarvisvm.extrace_info()' to extract the information from the search results.The returned url(output) is always stored with key 'search_results.seqnum1' in the key-value store.


output should be a json object with the following structure:
```json
{
  "goal": "Acquire the current weather data for San Francisco and provide suggestions based on temperature, show me in a web page.",
  "thoughts_on_break_down":"",
  "raw_task_list": [...],
  "instructions": [ 
    {
        "seqnum":1,
        "type":"RunPython",
        "python_code":"", // must have
        "reasoning":"", // must have, why choose or not choose extract_info or search_online or text_completion inside the python code
        "analysis_on_how_python_code_works":"", // must have, how the python code works, how it use jarvisvm API
        ...
    },
    {
        "seqnum":2,
        ...
    }
    ...
  ]
  "reasoning_for_text_completion_api":  // must have
}

"""



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

def translate_plan_to_instructions(plan: str, model: str):
    try:
        user_prompt = (
            f"Please provide an instruction list. Our goal is to translate the plan:\n\n```json\n{plan}\n```\n\n"
            "into instructions for JarvisVM.\n\n"
            "Feel free to think outside the task list and be flexible and smart in your approach.\n"
            "Your JSON response should be:\n\n```json"
        )

        resp = gpt.complete_with_system_message(sys_prompt=TRANSLATE_PLAN_SYS_PROMPT, user_prompt=user_prompt, model=model)
        logging.info("Response from AI: %s", resp)
        return resp

    except Exception as err:
        logging.error("Error in main: %s", err)
        time.sleep(1)