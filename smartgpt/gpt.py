import os
import time
from typing import Optional
import openai
import tiktoken

# OpenAI API for Azure
#openai.api_type = "azure"
#openai.api_base = "https://pingcat-bot.openai.azure.com/"
#openai.api_version = "2023-03-15-preview"

openai.api_key = os.getenv("OPENAI_API_KEY")

# Constants
TOKEN_BUFFER = 50
COMBINED_TOKEN_LIMIT = 8192 - TOKEN_BUFFER
MAX_RESPONSE_TOKENS = 1000
MAX_REQUEST_TOKENS = COMBINED_TOKEN_LIMIT - MAX_RESPONSE_TOKENS
TOKENS_PER_MESSAGE = 3
TOKENS_PER_NAME = 1
USER_INPUT_SUFFIX = "Determine which next task to use by reading memory section, and write one valid action, both according to the specified schema:"

# Default model
GPT_4 = "gpt-4"
#GPT_4 = "gpt-4_playground"

# Alternative model
GPT_3_5_TURBO = "gpt-3.5-turbo"
#GPT_3_5_TURBO = "gpt-35-turbo_playground"

def max_token_count(model:str = GPT_4) -> int:
    if model == GPT_3_5_TURBO:
        return 4096 
    return 8192


def chat(goal: str, general_directions: str, new_plan: Optional[str], task_desc, model: str = GPT_4):
    system_message = {"role": "system", "content": f"{general_directions}"}
    user_message_content = USER_INPUT_SUFFIX
    if new_plan is not None:
        user_message_content = f"Change your plan to: {new_plan}\n{user_message_content}"

    user_message = {"role": "user", "content": f"user's request:{goal}\n {user_message_content}\n{task_desc}"}

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
            #print(f"message sent to AI: {messages}")
            response = openai.ChatCompletion.create(model=model, messages=messages, max_tokens=max_response_tokens, temperature=0.7)
            #time.sleep(1)
            return response.choices[0].message["content"]  # type: ignore
        except openai.error.RateLimitError:  # type: ignore
            print(f"Model {model} currently overloaded. Waiting 30 seconds...")
            time.sleep(30)

def revise(text: str, model: str = GPT_3_5_TURBO):
    messages = [
        {
            "role": "system",
            "content": "You are a task assistant. You will revise the a goal to make it more clear for executing.",
        },
        {"role": "user", "content": text[:4096]},
    ]
    
    request_token_count = count_tokens(messages)
    max_response_token_count = 4096 - request_token_count

    return send_message(messages, max_response_token_count, model=model)