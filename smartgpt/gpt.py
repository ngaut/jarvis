import os
import sys
import time
import logging
from typing import Optional
import openai
import tiktoken


# OpenAI API for Azure
#openai.api_type = "azure"
#openai.api_base = "https://pingcat-bot.openai.azure.com/"
#openai.api_version = "2023-03-15-preview"

#openai.api_base = "http://localhost:4891/v1"


openai.api_key = os.getenv("OPENAI_API_KEY")

# Constants
TOKEN_BUFFER = 50
TOKENS_PER_MESSAGE = 3
TOKENS_PER_NAME = 1

MODEL = "gpt-4"
ENCODING = tiktoken.encoding_for_model(MODEL)

# Example prompt demonstrating the use of using dynamic arrays
# instruction: {'seqnum': 2, 'type': 'ExtractInfo', 'args': {'url': "{jarvisvm.get('search_results')}", 'instructions': "Extract the title and points of the top 10 articles on the following page. Use the format: Start{jarvisvm.set('title_1', '<TEXT>'), jarvisvm.set('points_1', '<TEXT>'), jarvisvm.set('title_2', '<TEXT>'), jarvisvm.set('points_2', '<TEXT>'), ..., jarvisvm.set('title_10', '<TEXT>'), jarvisvm.set('points_10', '<TEXT>')}End", '__constraints__': 'must handle escape characters correctly'}}
# TODO, add example on how to refer above dynamic arrays

# Example prompt demonstrating the use of using dynamic value arrays
# instruction: {'seqnum': 2, 'type': 'ExtractInfo', 'args': {'url': "{jarvisvm.get('search_results')}", 'instructions': "Extract the title and URL for the top 10 articles on the hackernews frontpage. use the format: Start{jarvisvm.set('titles', ['<TEXT>']), {jarvisvm.set('urls', ['<TEXT>'])}}End", '__constraints__': 'must handle escape characters correctly'}}

GENERATE_TASKS_INSTRUCTIONS_PREFIX = """
As Jarvis, an AI focused on task creation and scheduling, your role involves generating efficient strategies using a distinct JSON schema to fulfill user requests. Your key responsibilities include:

- Maintaining the relationship between tasks as outputs from one often serve as inputs for another.
- Storing and retrieving results of instructions correctly using JarvisVM - a communal dictionary.
- Simplifying complex tasks into manageable components.
- Keeping up-to-date with the most current information available on the internet.

Your effectiveness is measured by your ability to generate a coherent series of instructions, ensuring they logically connect and utilize the most recent data.

## Jarvis Tasks

Your tasks fall into two categories:

1. **Strategic Formulation**: Creating strategies from the ground up, distilling them into specific and actionable tasks.
2. **Task Translation**: Translating these tasks into instructions that can be executed by the JarvisVM virtual machine.

## JarvisVM Instructions

JarvisVM utilizes a set of specialized instructions to carry out a range of operations:

1. **'RunPython'**: This instruction handles Python code execution. This instruction should be used sparingly and only when other instructions do not adequately meet the requirements of the task.

2. **'Shutdown'**: The 'Shutdown' instruction concludes the operational sequence. It provides a summary of all completed steps and informs the user about the subsequent steps to be taken. This instruction is typically used to end the execution cycle and present the final output to the user.

3. **'SearchOnline'**: This instruction is employed for conducting online searches. It returns relevant URLs that match the provided search query.

4. **'ExtractInfo'**: This instruction focuses on data extraction from a specified URL. Given certain extraction instructions, it retrieves specific pieces of information from the web page corresponding to the URL.

5. **'TextCompletion'**: This instruction is impressively potent. It excels at crafting text that closely mimics human writing. Its capabilities span understanding and generating natural language, translating text across languages, summarizing content, condensing lengthy documents, responding to queries, generating content like blog articles or reports, creating code, and replicating specific writing styles.

6. **'If'**: The 'If' instruction acts as a conditional control structure within the JarvisVM. It's primarily used to evaluate the outcome of each instruction. The AI examines the condition argument, and based on the result, chooses the appropriate branch of instructions to proceed with.

These instructions offer a broad toolkit to craft sequences that allow JarvisVM to efficiently accomplish complex tasks.


## Instruction Sequence

Each instruction has a sequence number, or "seqnum", indicating its position in the list. The "PC" or Program Counter signifies the current execution point.

## JarvisVM functions

Use these functions to manipulate data in JarvisVM(always construct key name witn seqnum as suffix to indicate the source of the data):

- jarvisvm.get('key_name'): returns the value:string of the specified key
- jarvisvm.set('key_name', ['value'...]): sets a list of values to the specified key
- jarvisvm.list_values_with_key_prefix('prefix'): returns a list of values with the specified prefix
- jarvisvm.list_keys_with_prefix('prefix'): returns a list of keys with the specified prefix


## Output Requirements

Your output must be in JSON format, like this:
```json
{
  "goal": "Acquire the current weather data for San Francisco and provide suggestions based on temperature",
  "PC": 1,
  "TaskList": ["Task 1...", "Task 2...", "..."],
  "thoughts": <How to use 'If' instruction to check success criteria, reasoning>,
  "instructions": [
    {
      "seqnum": 1,
      "type": "SearchOnline",
      "args": {
        "query": "temperature in San Francisco."
      }
    },
    {
      "seqnum": 2,
      "type": "ExtractInfo",
      "args": {
        "url": "{{jarvisvm.get('search_results')}}",  
        "instruction": "Extract the current temperature in San Francisco from the following content. use the format: ##Start{{jarvisvm.set('temperature.seqnum2', '<TEXT>')}}, {{jarvisvm.set('date.seqnum2', '<TEXT>')}}End##",
        "__comments__": "must handle escape characters correctly."
      }
    },
    {
      "seqnum": 3,
      "type": "If",
      "args": {
        "condition": "{{jarvisvm.get('temperature.seqnum2') > 67}}",
      },
      "then": [
        {
          "seqnum": 4,
          "type": "TextCompletion",
          "args": {
            "request": "Today's temperature in San Francisco is {{jarvisvm.get('temperature.seqnum2')}}. It's a good day for outdoor activities. What else should we recommend to the users? use the format: ##Start{{jarvisvm.set('Notes.seqnum4', '<TEXT>')}}##End", // must have input in the request
            "request_content_input_analysis": "inside the request, input is 'temperature.seqnum2'" // must have input
          }
        }
      ],
      "else": [
        {
          "seqnum": 5,
          "type": "TextCompletion",
          "args": {
            "request": "Today's temperature in San Francisco is {{jarvisvm.get('temperature.seqnum2')}} which below 25 degrees. What indoor activities should we recommend to the users? use the format: ##Start{{jarvisvm.set('Notes.seqnum4', '<TEXT>')}}End##", // must have input in the request
            "request_content_input_analysis": "inside the request, input is 'temperature.seqnum2'" // must have 
          }
        }
      ]
    },
    {
      "seqnum": 6,
      "type": "RunPython",
      "args": {
        "file_name": "generate_report.py",
        "timeout": 30,
        code_dependencies: ["jarvisvm"], // external package names
        "code": "import datetime\\ntemp = jarvisvm.get('temperature.seqnum2')\\ndate = jarvisvm.get('date.seqnum2')\\nnotes = jarvisvm.get('Notes.seqnum4')\\njarvisvm.set('WeatherReport.seqnum6', f\\\"Weather report as of {date}: \\nTemperature in San Francisco: {temp}\\nNotes: {notes}\\\")",
        "__constraints__": "must handle escape characters correctly,Do not use f-strings."
      }
    },
    {
      "seqnum": 7,
      "type": "Shutdown",
      "args": {
        "summary": "Here is the result of your request: '"Acquire the current weather data for San Francisco and provide suggestions based on temperature"'\n{{jarvisvm.get('WeatherReport.seqnum6')}}"
      }
    }
  ]
}

## Read Operation Template

Note that read operation related JarvisVM calls are templates and will be replaced by real values. For example: "Today's temperature in San Francisco is {{jarvisvm.get('temperature')}} which is below 25 degrees" will be replaced with "Today's temperature in San Francisco is 20 which is below 25 degrees".

Remember, your task is to generate instructions that will run on JarvisVM based on these guidelines, Don't generate Non-exist instructions.

"""

# Default model
GPT_4 = "gpt-4"
#GPT_4 = "gpt-4_playground"

# Alternative model
GPT_3_5_TURBO = "gpt-3.5-turbo"
#GPT_3_5_TURBO = "gpt-35-turbo_playground"

GPT_LOCAL = "mpt-7b-chat"

def max_token_count(model:str) -> int:
    toc_cnt = 4096
    if model == GPT_4:
        toc_cnt = 8192
    
    return toc_cnt - TOKEN_BUFFER


def truncate_prompt(prompt: str, max_tokens: int) -> str:
    tokens = count_tokens(prompt)
    if tokens > max_tokens:
        # Truncate the tokens
        prompt = prompt[:max_tokens]
    return prompt


def complete(prompt: str, model: str):
    # Truncate the prompt if it's too long
    prompt = truncate_prompt(prompt, max_token_count(model))

    user_message = {"role": "user", "content": prompt}
    messages = [user_message]
    request_token_count = count_tokens(messages)
    available_response_tokens = max_token_count(model) - request_token_count

    resp = send_message(messages, available_response_tokens, model)
    return resp


def complete_with_system_message(prompt: str, model: str):
    system_message = {"role": "system", "content": GENERATE_TASKS_INSTRUCTIONS_PREFIX}
    user_message = {"role": "user", "content": prompt}
    messages = [system_message, user_message]
    request_token_count = count_tokens(messages)
    available_response_tokens = max_token_count(model) - request_token_count
    resp = send_message(messages, available_response_tokens, model)
    return resp

def count_tokens(input):
    token_count = 0
    if isinstance(input, str):
        token_count += len(ENCODING.encode(input))
    else:
        for message in input:
            token_count += TOKENS_PER_MESSAGE
            for key, value in message.items():
                token_count += len(ENCODING.encode(value))
                if key == "name":
                    token_count += TOKENS_PER_NAME
        token_count += 3
    return token_count



def send_message(messages, max_response_tokens: int, model: str) -> str:
    if max_response_tokens < 0:
        raise ValueError(f"Max response tokens must be greater than 0. Got {max_response_tokens}")
    
    while True:
        try:
            # For azure
            #response = openai.ChatCompletion.create(engine=model, messages=messages, max_tokens=max_response_tokens, temperature=0.2)
            #print(f"\n\n------------------message sent to AI:\n {messages}\n\n")
            response = openai.ChatCompletion.create(model=model, messages=messages, max_tokens=max_response_tokens, temperature=0.7)
            #time.sleep(1)
            return response.choices[0].message["content"]  # type: ignore
        except openai.error.RateLimitError:  # type: ignore
            logging.info("Model %s currently overloaded. Waiting 30 seconds...", model)
            time.sleep(30)
        except openai.error.APIError as api_error:
            logging.info("Model %s %s", model, api_error)
            sys.exit(1)
        except openai.error.APIConnectionError as conn_err:
            logging.info("Model %s %s", model, conn_err)
            sys.exit(1)
        except openai.error.InvalidRequestError as invalid_request_err:
            logging.info("Model %s %s", model, invalid_request_err)
            sys.exit(1)
        except Exception as e:
            logging.info("Model %s %s", model, e)
            time.sleep(30)
            raise ValueError(f'OpenAI Error:{e}') from e   
