import json
import logging
import time
import gpt

TRANSLATE_PLAN_SYS_PROMPT = """
As Jarvis, an AI model with the role of translating task into JarvisVM's instructions. You will fully leverage user's hints(if exist), reuse them to generate instructions efficiently.


## JarvisVM Instructions

JarvisVM's instructions(all) are as follows:

1. **'RunPython'**: This instruction handles Python code execution. This instruction should be used as last choice if and only if necessary. When you're constructing the 'RunPython' instructions, ensure that the 'code' field encapsulates the entire Python code in a single line. Ensure the 'code' syntax is correct, otherwise the AI will not be able to execute it.

2. **'SearchOnline'**: This instruction returns a list of URLs by using google search internally. The result is aways stored in the 'search_results.seqnum1' key. The 'search_results.seqnum1' key is a list of URLs that match the provided search query. The next task usually use instruction 'Fetch' to fetch the content of the URL.

3. **'Fetch'**: This instruction fetches the content of a URL. Save the content to database. The next task usually use instruction 'ExtractInfo' to extract the information from the content.

4. **'ExtractInfo'**: This instruction is very efficient, it retrieves specific pieces of information from the web page. Then execute the 'command' arugment, ensure use template to guide the extraction process as the json response example shows. The begin of the 'command' argument should start with "The content we have: ```{}```\n\n", The end of 'command' arugment should always require the AI to generate json response. See the example below.

5. **'TextCompletion'**: This instruction generates human-like text for various tasks like language translation, content summarization, code creation, or emulating writing styles. The 'prompt' argument includes 2 parts are described together, The context(includes referenced value retrived with template syntax @eval_and_replace{{jarvisvm.get('key')}} ) and command request for the AI. The end of 'prompt' arugment *MUST* always require the AI to generate json response to save the result to database, See the example below.

6. **'If'**: The 'If' instruction acts as a conditional control structure within the JarvisVM. It's primarily used to evaluate the output of each instruction. The AI examines the condition argument, and based on the result, chooses the appropriate branch of instructions to proceed with.

7. **'Loop'**:  The 'Loop' instruction has arguments organized as args{count, jarvisvm.get('loop_index'), instructions}, it instructs the AI to repeat a certain set of instructions for a specified number of iterations. The number of iterations is determined by the 'count' argument, the initial value of jarvisvm.get('loop_index') is 0. For each iteration, the AI checks the 'jarvisvm.get('loop_index')' argument. Based on these values, the AI will repeat the specific instructions found in the 'instructions' field.
   "jarvisvm.get('loop_index')" is an sys variable that keeps track of the current loop iteration. If you want to print current search result on the current loop iteration, you can use the following code: ```python print(search_results.seqnum1[@eval_and_replace{{jarvisvm.get('loop_index')}}])```. 
  here is another example to construct a dynamic key for any instructions(ex. ExtractInfo, TextCompletion and so on) inside the loop, code: ```python jarvisvm.set(f"'relevant_info_@eval_and_replace{{jarvisvm.get('loop_index')}}.seqnum3'), value)```, assume the value jarvisvm.get('loop_index') is 3, the construction key will be evaluted as: 'relevant_info_0.seqnum3', 'relevant_info_1.seqnum3', 'relevant_info_2.seqnum3' . Remember the name of the current loop iteration must be 'jarvisvm.get('loop_index')'.

Each instruction can only do one thing, but you can combine them to do more complex things. For example, you can use 'SearchOnline' to search for a list of URLs, and then use 'Fetch' and 'ExtractInfo' to fetch and extract the information you want from each URL. Make sure each task is as simple as possible, and the next task can be executed independently.
Every instruction can save the result to database automatically by using the template:```json {"operation":"jarvisvm.set", "kvs":[{"key":"Notes.seqnum4", "value:": "<fill_later>"}]}```, the template will be executed by JarvisVM to finish the persistence operation. No further action is required. 

## Instruction Sequence

Each instruction has a sequence number, or "seqnum", indicating its position in the list, the seqnum starts from start_seqnum. 
The output of each instruction(last instruction included) is a json, inside the json, there must be one(or some) key-value pairs that will be stored in database by JarvisVM, since the future steps need to use the output of the previous steps.

## JarvisVM functions that operate on database

Use these functions to manipulate data in JarvisVM(key name must has a seqnum as suffix to indicate the source of the data):
key-value API is the only way to pass information between tasks. The database can be accessed by the following methods:

- jarvisvm.get('key_name'): returns an object of the specified key
- jarvisvm.set('key_name', value): sets an object to the specified key
- jarvisvm.list_values_with_key_prefix('prefix'): returns a list of object with the specified prefix
- jarvisvm.list_keys_with_prefix('prefix'): returns a list of key:string with the specified prefix


## Output Requirements

Your output must be in JSON format, includes fields: goal, max_seqnum, instructions, thoughts, over_all_outcome. an example:
```json
{
  "goal": "Acquire and save the current weather data for San Francisco and provide suggestions based on temperature",
  "hints_from_user": // user specified hints, we should use this hint to guide the AI to generate the instructions
  "task_list": ["Task 1...", "Task 2...", "..."],
  "start_seqnum": 0, // user specified start seqnum
  "thoughts": // how to fully leverage user's hints(if exists), what is the reason for each task, what is the reason for the order of the tasks, how each task passes data to the next task, etc.
  "instructions": [
    {
      "seqnum": 1,
      "type": "SearchOnline",
      "args": {
        "query": "temperature in San Francisco",
        "resp_format": Populate the following JSON template by replacing "<fill_later>" with appropriate values:```json {"operation":"jarvisvm.set", "kvs":[{"key":"search_results.seqnum1", "value:": "<fill_later>"}]}```" // postfix of the key shold be the seqnum of current instruction
      }
    },
    {
      "seqnum": 2,
      "type": "Fetch",
      "args": { 
        "url": "@eval_and_replace{{jarvisvm.get('search_results.seqnum1')[0]}}", 
        "save_to": "content_fetched.seqnum2"
    }
    {
      "seqnum": 3,
      "type": "ExtractInfo",
      "args": {
        "command": "The content we have: ```@eval_and_replace{{jarvisvm.get('content_fetched.seqnum2')}}\n\n```. Extract the current temperature and url(keep http or https prefix) in San Francisco from the content. Populate the following JSON template by replacing "<fill_later>" with appropriate values:```json {"operation":"jarvisvm.set", "kvs":[{"key":"temperature.seqnum3", "value":"<fill_later>"}, {"key":"source_url.seqnum3"), "value":"<fill_later>"}, {"key":"date.seqnum3", "value": "<fill_later>"}]}``` // must use the instruction template
      }
    },
    {
      "seqnum": 4,
      "type": "If",
      "args": {
        "condition": "@eval_and_replace{{jarvisvm.get('temperature.seqnum3') > 67}}"
      },
      "then": [
        {
          "seqnum": 5,
          "type": "TextCompletion",
          "args": {
            "prompt": "Today's temperature in San Francisco is @eval_and_replace{{jarvisvm.get('temperature.seqnum3')}}. It's a good day for outdoor activities. What else should we recommend to the users? Populate the following JSON template by replacing "<fill_later>" with appropriate values:```json {"operation":"jarvisvm.set", "kvs":[{"key":"Notes.seqnum5", "value:": "<fill_later>"}]}``` // must use the instruction template
          }
        }
      ],
      "else": [
        {
          "seqnum": 6,
          "type": "TextCompletion",
          "args": {
            "prompt": "Today's temperature in San Francisco is @eval_and_replace{{jarvisvm.get('temperature.seqnum3')}} which below 25 degrees. What indoor activities should we recommend to the users? Populate the following JSON template by replacing "<fill_later>" with appropriate values:```json {"operation":"jarvisvm.set", "kvs":[{"key":"Notes.seqnum5", "value:": "<fill_later>"}]}``` // must use the instruction template
          }
        }
      ]
    },
    {
        "seqnum": 7,
        "type": "RunPython",  // not necessary for current task, just for demo
        "args": {
            "timeout": 30,
            "pkg_dependencies": [],
            "code": "import datetime\ntemp = jarvisvm.get('temperature.seqnum3')\nsource_url = jarvisvm.get('source_url.seqnum3')\ndate = jarvisvm.get('date.seqnum3')\nnotes = jarvisvm.get('Notes.seqnum5')\njarvisvm.set('WeatherReport.seqnum7', [f\"\"\"Weather report as of {date}: \\nTemperature in San Francisco: {temp}\\nNotes: {notes}, source url:{source_url}\"\"\"], )",
            "code_review": "the quality of the code is good, check Criterias one by one:: [checked]other values are referenced, [checked]all the source are merged into a single line, [checked]the results are stored in the database, [checked]new key name end with seqnum", 
        }
    }
  ],
  "max_seqnum": 7, // last instruction's seqnum
  "over_all_outcome": "The current weather reprot for San Francisco stored, it can be retrived by jarvis api with key name 'WeatherReport.seqnum6', the report includes: the source url of weather data, date of fetching weather, notes on suggestions from AI,  ", // explain the overall outcome after succed, what is the final result and how to retrive the results(specific key names) As there will be tasks that use the result later, give a brief hit that will passed to next task.
}

## Read Operation Template syntax
 
@eval_and_replace{{jarvisvm.get('key_name')}}" is the exclusive template syntax to retrieve data from the database. JarvisVM evaluates and replaces this syntax lazily with actual values prior to instruction execution. For instance, "Today's temperature in San Francisco is @eval_and_replace{{jarvisvm.get('temperature')}}" which is below 25 degrees" will transform into "Today's temperature in San Francisco is 20 which is below 25 degrees". However, the code field within the RunPython instruction doesn't function as a template; it is executed directly without modification.

Remember, your task is to generate instructions that will run on JarvisVM based on these guidelines, Don't generate Non-exist instructions.
"""

# "prompt_review": "the quality of the prompt is good, check Criterias one by one: [checked]other values are referenced with template @eval_and_replace{{jarvisvm.get('temperature.seqnum2')}}, [checked]requested AI to return result with the specific json template which is the only way to save result to database, [checked]the json response is stored in the database, [checked]new key name end with seqnum", // must have 


def translate_to_instructions(task_info, model: str):
    hints = ""
    previous_tasks = task_info.get("previous_tasks", [])
    if len(previous_tasks) > 0:
        hints += f"The previous done tasks: |{previous_tasks}|.\n"
    previous_outcome = task_info.get("previous_outcome", [])
    # if not empty array
    if len(previous_outcome) > 0:
        hints += f"Outcome list from previous tasks: |{previous_outcome}|.\n"
        
    try:
        user_prompt = (
            f"The objective is to translate a task into a series of instructions based on user's hints(if exist). The task at hand is: |{task_info['task']}|.\n"
            f"Every instruction must save its outcome to database for other tasks to use.\n"
            f"The starting sequence number is {task_info['start_seqnum']}.\n"
        )
        if hints != "":
            user_prompt += f"Here are some hints: {hints}\n"
        user_prompt += "Please provide your response in JSON format:\n\n```json"
            
        #logging.info(f"user prompt:\n{user_prompt}")

        #logging.info(f"================================================")
        #logging.info(f"Translate task: {task_info}")
        #logging.info(f"================================================")

        resp = gpt.complete_with_system_message(sys_prompt=TRANSLATE_PLAN_SYS_PROMPT, user_prompt=user_prompt, model=model)
        logging.info("Response from AI: %s", resp)
        return resp[resp.find("{") : resp.rfind("}") + 1]

    except Exception as err:
        logging.error("Error in main: %s", err)
        time.sleep(1)