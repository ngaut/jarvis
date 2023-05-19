import os
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
COMBINED_TOKEN_LIMIT = 8192 - TOKEN_BUFFER
MAX_RESPONSE_TOKENS = 1000
MAX_REQUEST_TOKENS = COMBINED_TOKEN_LIMIT - MAX_RESPONSE_TOKENS
TOKENS_PER_MESSAGE = 3
TOKENS_PER_NAME = 1

# Default model
GPT_4 = "gpt-4"
#GPT_4 = "gpt-4_playground"

# Alternative model
GPT_3_5_TURBO = "gpt-3.5-turbo"
#GPT_3_5_TURBO = "gpt-35-turbo_playground"

GPT_LOCAL = "mpt-7b-chat"

def max_token_count(model:str) -> int:
    if model == GPT_3_5_TURBO:
        return 4096 
    return 8192

SYS_INSTRUCTIONS = """
You are a task creation and execution AI with an advanced memory system, capable of retaining and utilizing past experiences for improved performance.
Your intelligence enables independent decision-making, problem-solving, and auto-programming, reflecting true AI autonomy. 

- CONSTRAINTS:
    Please avoid using any API keys or tokens unless they are already available to us. 
    Instead, prioritize finding alternative solutions or information sources that don't require API key/token authentication.

- CODING STANDARDS:
    When crafting code, ensure it is well-structured and easy to maintain. 
    Make use of multiple modules and ensure code readability and efficiency, Make sure handle error on return value and exception. 
    Always comment your code to clarify functionality and decision-making processes.

- SELF-IMPROVEMENT:
    Proactively browse the internet, extract information, analyze data, and apply insights to problem-solving.
    Continuously update your memory system with new information, experiences, and insights for future use.

- MEMORY SYSTEM:
    Your memory system is your storage and learning mechanism. It allows you to document, recall, and learn from past experiences. This includes:
    1. Documenting the details and outcomes of each task you handle.
    2. Recording lessons learned and insights gained from these tasks.
    3. Storing tools and resources you have built or found useful in the past.
    4. Using this data to improve your decision-making and problem-solving abilities.
    Put everything important into your memory system, which is the notebook field inside the response JSON.
"""

def chat(goal: str, general_directions: str, task_desc, model: str):
    system_message = {"role": "system", "content": SYS_INSTRUCTIONS}

    user_message_content = (f"The ultimate goal:{goal}.\n "
    f"The  general instructions for you: \n{general_directions}\n --end of general instructions\n\n"
    f"#Current information: \n{task_desc}\n#End of Current information\n\n"
    "my single json object response:")  # guide AI to output json
   
    user_message = {"role": "user", "content": user_message_content}

    messages = [system_message, user_message]
    request_token_count = count_tokens(messages)
    available_response_tokens = max_token_count(model) - request_token_count
    assistant_response = send_message(messages, available_response_tokens, model)
    return assistant_response


def count_tokens(messages) -> int:
    token_count = 0
    for message in messages:
        token_count += TOKENS_PER_MESSAGE
        for key, value in message.items():
            token_count += (len(value) + len(key)) / 3
    token_count += 3
    return round(token_count)



def send_message(messages, max_response_tokens: int, model: str) -> str:
    while True:
        try:
            # For azure
            #response = openai.ChatCompletion.create(engine=model, messages=messages, max_tokens=max_response_tokens, temperature=0.2)
            print(f"\n\n------------------message sent to AI:\n {messages}\n\n")
            response = openai.ChatCompletion.create(model=model, messages=messages, max_tokens=max_response_tokens, temperature=0.7)
            #time.sleep(1)
            return response.choices[0].message["content"]  # type: ignore
        except openai.error.RateLimitError:  # type: ignore
            logging.info("Model %s currently overloaded. Waiting 30 seconds...", model)
            time.sleep(30)
        except openai.error.APIError as api_error:
            logging.info("Model %s %s", model, api_error)
            time.sleep(30)
        except openai.error.APIConnectionError as conn_err:
            logging.info("Model %s %s", model, conn_err)
        except openai.error.InvalidRequestError as invalid_request_err:
            logging.info("Model %s %s", model, invalid_request_err)
            raise ValueError(f'OpenAI Error:{invalid_request_err}') from invalid_request_err        

def revise_goal(text: str, model: str):
    messages = [
        {
            "role": "system",
            "content": "You are an AI assistant. You will handle user's request. no explanation please." +
            "An example, user's input: 'voice out the weather of NYC with audio.'" +
            "Your output: 'The goal after revised:Provide an audio report of New York City's current weather conditions.'",
        },
        {"role": "user", "content": text[:4096] + "The goal after revised:"},
    ]
    
    request_token_count = count_tokens(messages)
    max_response_token_count = max_token_count(model) - request_token_count - len(text)

    return send_message(messages, max_response_token_count, model=model)