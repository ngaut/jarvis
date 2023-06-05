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


def complete_with_system_message(sys_prompt: str, user_prompt: str, model: str):
    system_message = {"role": "system", "content": sys_prompt}
    user_message = {"role": "user", "content": user_prompt}
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
