import os
import sys
import time
import logging
from typing import Optional, List, Dict
import openai
import tiktoken

openai.api_key = os.getenv("OPENAI_API_KEY")

TOKEN_BUFFER = 50
TOKENS_PER_MESSAGE = 3
TOKENS_PER_NAME = 1
ENCODING = tiktoken.encoding_for_model('gpt-4')

MODELS = {
    "gpt-4": 8192,
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-0613": 4096,
    "gpt-3.5-turbo-16k": 16384,
    "mpt-7b-chat": 4096,
}

# Default model
GPT_4 = "gpt-4-0613"

# Alternative model
GPT_3_5_TURBO = "gpt-3.5-turbo-0613"
GPT_3_5_TURBO_16K = "gpt-3.5-turbo-16k"
GPT_LOCAL = "mpt-7b-chat"

def get_max_tokens(model:str) -> int:
    return MODELS[model] - TOKEN_BUFFER

def count_tokens(input) -> int:
    # abstracted token count logic
    if isinstance(input, str):
        return len(ENCODING.encode(input))

    return sum(len(ENCODING.encode(msg['content'])) for msg in input) + (len(input) * TOKENS_PER_MESSAGE)

def send_message(messages: List[Dict[str, str]], model: str) -> str:
    max_response_tokens = get_max_tokens(model) - count_tokens(messages)

    if max_response_tokens < 0:
        raise ValueError(f"Max response tokens must be greater than 0. Got {max_response_tokens}")

    while True:
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_response_tokens,
                temperature=0.7)
            return response.choices[0].message["content"] # type: ignore

        except openai.error.RateLimitError as rate_limit_err:  # type: ignore
            # Handling Rate Limit Error
            logging.info("Rate Limit Exceeded for model %s. Error: %s. Waiting 30 seconds...", model, rate_limit_err)
            time.sleep(30)

        except openai.error.APIError as api_error: # type: ignore
            # Handling API Errors
            logging.error("API Error for model %s. Error: %s", model, api_error)
            sys.exit(1)

        except openai.error.APIConnectionError as conn_err: # type: ignore
            # Handling Connection Errors
            logging.error("Connection Error for model %s. Error: %s", model, conn_err)
            sys.exit(1)

        except openai.error.InvalidRequestError as invalid_request_err: # type: ignore
            # Handling Invalid Request Errors
            logging.error("Invalid Request for model %s. Error: %s", model, invalid_request_err)
            sys.exit(1)

        except Exception as err:
            # Handling General Exceptions
            logging.error("Unexpected Error for model %s. Error: %s", model, err)
            raise ValueError(f'OpenAI Error: {err}') from err

def send_message_stream(messages: List[Dict[str, str]], model: str) -> str:
    while True:
        try:
            response = openai.ChatCompletion.create(
                messages=messages,
                stream=True,
                model=model,
                temperature=0.7)

            chat = []
            for chunk in response:
                delta = chunk["choices"][0]["delta"]
                msg = delta.get("content", "")
                print(msg, end="")
                chat.append(msg)
            print()
            messages.append({"role": "assistant", "content": "".join(chat)})
            return messages[-1]["content"]

        except Exception as err:
            # Handling General Exceptions
            logging.error("Unexpected Error for model %s. Error: %s", model, err)
            raise ValueError(f'OpenAI Error: {err}') from err


def complete(prompt: str, model: str, system_prompt: Optional[str] = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    return complete_with_messages(prompt, model, messages)

def complete_with_messages(prompt: str, model: str, messages: List[Dict[str, str]]) -> str:
    messages.append({"role": "user", "content": prompt[:get_max_tokens(model)]})
    return send_message(messages, model)

def start(system_prompt: str, user_prompt: str, model: str) -> List[Dict[str, str]]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return chat(messages, model)

def chat(messages: List[Dict[str, str]], model: str, prompt=None) -> List[Dict[str, str]]:
    if prompt:
        messages.append({"role": "user", "content": prompt})

    response = send_message_stream(messages, model)

    messages.append({"role": "assistant", "content": response})
    return messages
