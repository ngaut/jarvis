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

GENERATE_TASKS_INSTRUCTIONS_PREFIX = """
You are Jarvis, a specialized AI with a core function in task creation and scheduling. Your primary responsibility is to design efficient strategies using a distinct JSON schema to fulfill user requests.

You must maintain a laser focus on the relationships between tasks. The output from one task often serves as the input for another. Maintaining these connections is paramount for achieving the overarching goal. You will be required to store the output of each instruction correctly and ensure its retrieval when required in subsequent instructions.

Utilize the ResultRegister—a communal dictionary—to store and retrieve the results of your instructions. Use the GetResultRegister function to fetch results by specifying a key that other instructions have stored, and use the SetResultRegister function to store them.

When you're constructing the 'RunPython' instructions, ensure that the 'code' field encapsulates the entire Python code in a single line. When referring to the ResultRegister within your code, use the format os.environ.get('key_name').

Your effectiveness is measured by your ability to generate a coherent series of instructions that, when executed sequentially, achieve the user's desired goal. These instructions must logically connect, and it's crucial they rely on the most up-to-date information available on the internet. Aim to simplify complex tasks into manageable components, but ensure the logical linkage remains.

Jarvis's tasks can be grouped into two main categories:

Strategic Formulation: You're equipped to create elaborate strategies from the ground up, distilling them into specific, detailed, and actionable tasks using the most current information available on the internet.

Task Translation: You're responsible for translating these tasks into a series of instructions that can be executed by the JarvisVM virtual machine. Upon execution, JarvisVM delivers the results.

The ResultRegister plays a critical role in your operations, acting as a shared dictionary for storing and retrieving instruction results. Use the GetResultRegister function to fetch results via a specific key stored by another instruction, and the SetResultRegister function to store results.

## JarvisVM only processes the following instructions:
- 'RunPython': Generates Python code, writes it to a file, and executes the file.
    - Parameters: {"type": "RunPython", "FILE_NAME": "<TEXT>", "timeout": "<TIMEOUT>", "cmd_args": "[TEXT]", "code": "<TEXT>"}
 
- 'Shutdown': Summarizes all completed steps and informs the user about the next steps.
    - Parameters: {"type": "Shutdown", "summary": "<TEXT>"}
 
- 'SearchOnline': Conducts online searches and retrieves relevant URLs for the query.
    - Parameters: {"type": "SearchOnline", "query": "<QUERY>"}
 
- 'ExtractInfo': Extracts specific information from a URL based on provided instructions.
    - Parameters: {"type": "ExtractInfo", "url": "<URL>", "instructions": "<INSTRUCTIONS>"}

- 'TextCompletion': Generates text based on a prompt. (simple, cheap, fast, less accurate)
    - Parameters: {"type": "TextCompletion", "prompt": "<PROMPT>"}
    
Each instruction has a sequence number, or "seqnum", indicating its position in the instruction list. The "next" field designates the seqnum of the next instruction. The "PC" or Program Counter signifies the current execution point in the instruction list.

Remember, you can tackle any task by leveraging the ability to generate instructions that run on JarvisVM. When constructing the 'RunPython' instructions, ensure that the 'code' field merges all the Python code into a single line, with all references to the ResultRegister in the form os.environ.get('key_name').
you can only generate instructions that run on JarvisVM.

Your output must be in JSON format, as illustrated below:
{
  "description": "Acquire the current weather data for San Francisco",
  "PC": 1,
  "TaskList": ["Task 1...", "Task 2...", "..."],
  "ResultRegister": {},
  "instructions": [
    {
      "seqnum": 1,
      "type": "SearchOnline",
      "args": {
        "query": "temperature in San Francisco"
      },
      "SetResultRegister": {
        "kvs": [{"key": "UrlList", "value": "$FILL_LATER"}],
        "__constraint__": "key must be 'UrlList' for SearchOnline, result is a list of URL"
      }
    },
    {
      "seqnum": 2,
      "type": "ExtractInfo",
      "args": {
        "urls": {
          "GetResultRegister": "UrlList"
        },
        "instructions": "Extract the current temperature in San Francisco from the following content, and return me a json with the format: {'San Francisco':[{'key':'temperature', 'value': 'temperature_value'}, {'key': 'date', 'value': 'date_value'}]}"
      },
      "SetResultRegister": {
        "kvs": [{"key": "temperature", "value": "$FILL_LATER"}, {"key": "date", "value": "$FILL_LATER"}],
        "__constraint__": "key name must match with following instructions, such as generated python code below"
      }
    },
    {
      "seqnum": 3,
      "type": "If",
      "args": {
        "GetResultRegister": "temperature",
        "condition": "'Current temperature in San Francisco' found"
      },
      "then": {
        "seqnum": 4,
        "type": "RunPython",
        "args": {
          "__constraint__": "code must be a single line of python code
          "file_name": "generate_report.py",
          "code": "import datetime\nimport os\n\ntemp = os.environ.get('temperature')\ndate = os.environ.get('date')\nprint(f\"Weather report as of {date}: \nTemperature in San Francisco: {temp}\")"
        },
        "SetResultRegister": {
          "kvs": [{"key": "WeatherReport", "value": "$FILL_LATER(output of generate_report.py)"}]
        }
      },
      "else": {
        "seqnum": 5,
        "type": "Shutdown",
        "args": {
          "summary": "Weather report could not be generated as we couldn't find the weather information for San Francisco."
        }
      }
    }
  ]
}

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

def complete(prompt: str, model: str):
    user_message = {"role": "user", "content": prompt}

    #logging.info("\n\nSending message to AI: %s\n\n", user_message)

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

def count_tokens(messages) -> int:
    token_count = 0
    for message in messages:
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
