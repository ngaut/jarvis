import os
import sys
import time
import logging
from typing import Optional, List, Dict
import openai
import tiktoken

API_TYPE = os.getenv("OPENAI_API_TYPE")

# Set OpenAI or Azure API based on the OPENAI_API_TYPE
if API_TYPE == "azure":
    openai.api_type = API_TYPE
    openai.api_base = os.getenv("OPENAI_API_BASE")
    openai.api_version = os.getenv("OPENAI_API_VERSION")

openai.api_key = os.getenv("OPENAI_API_KEY")

try:
    TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
except (ValueError, TypeError):
    TEMPERATURE = 0.7


TOKEN_BUFFER = 50
TOKENS_PER_MESSAGE = 3
TOKENS_PER_NAME = 1
ENCODING = tiktoken.encoding_for_model("gpt-4")

MODELS = {
    "gpt-4": 8192,
    "gpt-4-0613": 8192,
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-0613": 4096,
    "gpt-3.5-turbo-16k": 16384,
    "mpt-7b-chat": 4096,
    "gpt-35-turbo-0613-azure": 4096,
    "gpt-35-turbo-16k-azure": 8192,
    "gpt-4-0613-azure": 8192,
    "gpt-4-32k-0613-azure": 32768,
}

if API_TYPE == "azure":
    GPT_4 = "gpt-4-0613-azure"
    GPT_3_5_TURBO = "gpt-35-turbo-0613-azure"
    GPT_3_5_TURBO_16K = "gpt-35-turbo-16k-azure"
else:
    GPT_4 = "gpt-4-0613"
    GPT_3_5_TURBO = "gpt-3.5-turbo-0613"
    GPT_3_5_TURBO_16K = "gpt-3.5-turbo-16k"

GPT_LOCAL = "mpt-7b-chat"


def get_max_tokens(model: str) -> int:
    return MODELS[model] - TOKEN_BUFFER


def count_tokens(input) -> int:
    # abstracted token count logic
    if isinstance(input, str):
        return len(ENCODING.encode(input))

    return sum(len(ENCODING.encode(msg["content"])) for msg in input) + (
        len(input) * TOKENS_PER_MESSAGE
    )


def truncate_to_tokens(content: str, max_token_count: int) -> str:
    """Truncates the content to fit within the model's max tokens."""

    if count_tokens(content) <= max_token_count:
        # No need to truncate
        return content

    tokens = ENCODING.encode(content)

    # Truncate tokens
    truncated_tokens = tokens[:max_token_count]

    # Convert truncated tokens back to string
    truncated_str = ENCODING.decode(truncated_tokens)

    return truncated_str


def send_messages(messages: List[Dict[str, str]], model: str) -> str:
    max_response_tokens = get_max_tokens(model) - count_tokens(messages)

    if max_response_tokens < 0:
        raise ValueError(
            f"Max response tokens must be greater than 0. Got {max_response_tokens}"
        )

    while True:
        try:
            if API_TYPE == "azure":
                response = openai.ChatCompletion.create(
                    engine=model,
                    messages=messages,
                    max_tokens=max_response_tokens,
                    temperature=TEMPERATURE,
                )
            else:
                response = openai.ChatCompletion.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_response_tokens,
                    temperature=TEMPERATURE,
                )

            logging.info(f"Call OpenAI: Model={model}, Total tokens={response.usage['total_tokens']}")  # type: ignore

            if model == GPT_4:
                logging.info("Sleeping for 60 seconds in GPT-4 model")
                time.sleep(60)

            return response.choices[0].message["content"]  # type: ignore

        except openai.error.RateLimitError as rate_limit_err:  # type: ignore
            # Handling Rate Limit Error
            logging.info(
                "Rate Limit Exceeded for model %s. Error: %s. Waiting 30 seconds...",
                model,
                rate_limit_err,
            )
            time.sleep(30)

        except openai.error.APIError as api_error:  # type: ignore
            # Handling API Errors
            logging.error("API Error for model %s. Error: %s", model, api_error)
            sys.exit(1)

        except openai.error.APIConnectionError as conn_err:  # type: ignore
            # Handling Connection Errors
            logging.error("Connection Error for model %s. Error: %s", model, conn_err)
            sys.exit(1)

        except openai.error.InvalidRequestError as invalid_request_err:  # type: ignore
            # Handling Invalid Request Errors
            logging.error(
                "Invalid Request for model %s. Error: %s", model, invalid_request_err
            )
            sys.exit(1)

        except Exception as err:
            # Handling General Exceptions
            logging.error("Unexpected Error for model %s. Error: %s", model, err)
            raise ValueError(f"OpenAI Error: {err}") from err


def send_messages_stream(messages: List[Dict[str, str]], model: str) -> str:
    while True:
        try:
            if API_TYPE == "azure":
                response = openai.ChatCompletion.create(
                    messages=messages,
                    stream=True,
                    engine=model,
                    temperature=TEMPERATURE,
                )
            else:
                response = openai.ChatCompletion.create(
                    messages=messages, stream=True, model=model, temperature=TEMPERATURE
                )

            chat = []
            for chunk in response:
                delta = chunk["choices"][0]["delta"]  # type: ignore
                msg = delta.get("content", "")
                print(msg, end="")
                chat.append(msg)
            print()
            messages.append({"role": "assistant", "content": "".join(chat)})
            return messages[-1]["content"]

        except Exception as err:
            # Handling General Exceptions
            logging.error("Unexpected Error for model %s. Error: %s", model, err)
            raise ValueError(f"OpenAI Error: {err}") from err


def complete(prompt: str, model: str, system_prompt: Optional[str] = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    else:
        messages.append({"role": "system", "content": "You are an AI agent."})

    return complete_with_messages(prompt, model, messages)


def complete_with_messages(
    prompt: str, model: str, messages: List[Dict[str, str]]
) -> str:
    messages.append({"role": "user", "content": prompt[: get_max_tokens(model)]})
    return send_messages(messages, model)


def start(system_prompt: str, user_prompt: str, model: str) -> List[Dict[str, str]]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return chat(messages, model)


def chat(
    messages: List[Dict[str, str]], model: str, prompt=None
) -> List[Dict[str, str]]:
    if prompt:
        messages.append({"role": "user", "content": prompt})

    response = send_messages_stream(messages, model)

    messages.append({"role": "assistant", "content": response})
    return messages
