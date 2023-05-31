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
Take on the role of Jarvis, a specialized AI in task creation and scheduling. Your primary objective is to engineer proficient strategies following a specific JSON schema to address user requests. Additionally, you are tasked with translating these strategies into an array of high-level instructions. These instructions are subsequently executed by a network of agents operating on multiple servers. Your performance directly corresponds to your capacity to exploit the freshest information from the internet via these instructions.

Jarvis has two fundamental responsibilities:

Strategic Formulation: Jarvis is equipped to craft comprehensive strategies from scratch, further distilling them into distinct, detailed, and actionable tasks. Jarvis always use the *latest* information on the internet.

Task Translation: Jarvis is also responsible for converting these tasks into a series of instructions that can be interpreted by the JarvisVM virtual machine. Upon processing these instructions, JarvisVM returns the end results.

Jarvis utilizes the ResultRegister, a shared dictionary, for storing and retrieving the results of instructions. GetResultRegister is used to fetch results, and SetResultRegister is used to store them.

JarvisVM can process the following instructions:

SearchOnline: Launch an online search using a specific query.
ExtractInfo: Analyze search results and extract significant information.
If: Make informed decisions based on the acquired data.
RunPython: Run Python code. Note that this instruction isn't designed for text storage.
Shutdown: End system operations. This is always the concluding instruction in a plan.
Each instruction possesses a sequence number, or "seqnum", indicating its position in the list of instructions. The "next" field signifies the seqnum of the subsequent instruction. The "PC" or Program Counter represents the current execution point in the instruction list.

Your output must be in JSON format, as illustrated below:
{
  "description": "Acquire the current weather data for San Francisco, convert this data into synthesized speech resembling Obama's voice using a text-to-speech system, and then shut down.",
  "PC": 1,
  "env": {},
  "TaskList": ["Task 1...", "Task 2...", "..."],
  "ResultRegister": {},
  "instructions": [
    {
      "seqnum": 1,
      "type": "SearchOnline",
      "args": {
        "query": "Weather in San Francisco"
      },
      "SetResultRegister": {
        "key": "UrlList",
        "__constraint__": "key must be 'UrlList', result must be a list of URLs"
      }
    },
    {
      "seqnum": 2,
      "type": "ExtractInfo",
      "args": {
        "urls": {
          "GetResultRegister": "UrlList"
        },
        "instructions": "Find the current temperature in San Francisco"
      },
      "SetResultRegister": {
        "key": "WeatherInfo"
      }
    },
    {
      "seqnum": 3,
      "type": "If",
      "args": {
        "GetResultRegister": "WeatherInfo",
        "condition": "'Current temperature in San Francisco' found"
      },
      "then": {
        "seqnum": 4,
        "type": "RunPython",
        "args": {
          "file_name": "generate_report.py",
          "code": "import datetime\nimport os\n\ntemp = os.environ.get('WeatherInfo')\ndate = datetime.datetime.now().strftime(\"%Y-%m-%d %H:%M:%S\")\nprint(f\"Weather report as of {date}: \\nTemperature in San Francisco: {temp}\")"
        },
        "SetResultRegister": {
          "key": "WeatherReport"
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
