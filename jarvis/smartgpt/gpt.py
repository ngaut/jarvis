import os
from typing import Optional, List, Dict
from dataclasses import dataclass, field

import openai
import tiktoken

from langchain.chat_models import ChatOpenAI
from langchain.llms.openai import OpenAI, AzureOpenAI
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.messages import (
    HumanMessage,
    SystemMessage,
    BaseMessage,
    ChatMessage,
)
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.embeddings.base import Embeddings

import jarvis.smartgpt.initializer  # ignore this line

GPT_4 = "gpt-4"
GPT_3_5_TURBO = "gpt-3.5-turbo"
GPT_3_5_TURBO_16K = "gpt-3.5-turbo-16k"
GPT_3_5_TURBO_INSTRUCT = "gpt-3.5-turbo-instruct"

## handle openai api arguments
API_TYPE = os.getenv("OPENAI_API_TYPE")

# Set OpenAI or Azure API based on the OPENAI_API_TYPE
if API_TYPE == "azure":
    azure_openai_model_kwargs = {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "api_version": os.getenv("OPENAI_API_VERSION"),
        "api_type": "azure",
        "api_base": os.getenv("OPENAI_API_BASE"),
    }
    azure_deployment_map = {
        "gpt-4": "gpt-4-0613-azure",
        "gpt-3.5-turbo": "gpt-35-turbo-0613-azure",
        "gpt-3.5-turbo-16k": "gpt-35-turbo-16k-azure",
        "text-embedding-ada-002": "text-embedding-ada-002-azure",
    }

try:
    TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
except (ValueError, TypeError):
    TEMPERATURE = 0.7


## define openai models
@dataclass
class ModelInfo:
    """Struct for model information.

    Would be lovely to eventually get this directly from APIs, but needs to be scraped from
    websites for now.
    """

    name: str
    max_tokens: int
    prompt_token_cost: float


@dataclass
class CompletionModelInfo(ModelInfo):
    """Struct for generic completion model information."""

    completion_token_cost: float


@dataclass
class ChatModelInfo(CompletionModelInfo):
    """Struct for chat model information."""

    supports_functions: bool = False


@dataclass
class EmbeddingModelInfo(ModelInfo):
    """Struct for embedding model information."""

    embedding_dimensions: int


OPEN_AI_CHAT_MODELS = {
    info.name: info
    for info in [
        ChatModelInfo(
            name="gpt-3.5-turbo-0613",
            prompt_token_cost=0.0015,
            completion_token_cost=0.002,
            max_tokens=4096,
            supports_functions=True,
        ),
        ChatModelInfo(
            name="gpt-3.5-turbo-16k-0613",
            prompt_token_cost=0.003,
            completion_token_cost=0.004,
            max_tokens=16384,
            supports_functions=True,
        ),
        ChatModelInfo(
            name="gpt-4-0613",
            prompt_token_cost=0.03,
            completion_token_cost=0.06,
            max_tokens=8191,
            supports_functions=True,
        ),
        ChatModelInfo(
            name="gpt-4-32k-0613",
            prompt_token_cost=0.06,
            completion_token_cost=0.12,
            max_tokens=32768,
            supports_functions=True,
        ),
    ]
}
# Set aliases for rolling model IDs
chat_model_mapping = {
    "gpt-3.5-turbo": "gpt-3.5-turbo-0613",
    "gpt-3.5-turbo-16k": "gpt-3.5-turbo-16k-0613",
    "gpt-4": "gpt-4-0613",
    "gpt-4-32k": "gpt-4-32k-0613",
}
for alias, target in chat_model_mapping.items():
    alias_info = ChatModelInfo(**OPEN_AI_CHAT_MODELS[target].__dict__)
    alias_info.name = alias
    OPEN_AI_CHAT_MODELS[alias] = alias_info

OPEN_AI_COMPLETION_MODELS = {
    info.name: info
    for info in [
        CompletionModelInfo(
            name="gpt-3.5-turbo-instruct",
            prompt_token_cost=0.0015,
            completion_token_cost=0.002,
            max_tokens=4097,
        ),
    ]
}

OPEN_AI_EMBEDDING_MODELS = {
    info.name: info
    for info in [
        EmbeddingModelInfo(
            name="text-embedding-ada-002",
            prompt_token_cost=0.0001,
            max_tokens=8191,
            embedding_dimensions=1536,
        ),
    ]
}

OPEN_AI_MODELS: dict[str, ChatModelInfo | EmbeddingModelInfo | CompletionModelInfo] = {
    **OPEN_AI_CHAT_MODELS,
    **OPEN_AI_COMPLETION_MODELS,
    **OPEN_AI_EMBEDDING_MODELS,
}

# tokenization helper function
TOKEN_BUFFER = 50
TOKENS_PER_MESSAGE = 4
ENCODING = tiktoken.encoding_for_model("gpt-4")


def get_max_tokens(model: str) -> int:
    return OPEN_AI_MODELS[model].max_tokens - TOKEN_BUFFER


def count_tokens(messages) -> int:
    # abstracted token count logic
    if isinstance(messages, str):
        return len(ENCODING.encode(messages))

    return sum(len(ENCODING.encode(item["content"])) for item in messages) + (
        len(messages) * TOKENS_PER_MESSAGE
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


## LLM helper functions
def create_chat_client(
    model: str,
    temperature: float = 0.7,
    use_azure: bool = False,
    deployment_engine: Optional[str] = None,
    model_kwargs: Optional[dict] = None,
) -> BaseLanguageModel:
    if use_azure:
        if deployment_engine is None:
            raise ValueError("Deployment engine must be specified for Azure API")
        if model_kwargs is None:
            raise ValueError(
                "Azure OpenAI model kwargs must be specified for Azure API"
            )
        return ChatOpenAI(
            client=openai.ChatCompletion,
            temperature=temperature,
            model_kwargs={
                "engine": deployment_engine,
                **model_kwargs,
            },
        )
    else:
        return ChatOpenAI(
            temperature=temperature,
            model=model,
            client=openai.ChatCompletion,
        )


def create_completion_client(
    model: str,
    temperature: float = 0.7,
    use_azure: bool = False,
    deployment_engine: Optional[str] = None,
    model_kwargs: Optional[dict] = None,
) -> BaseLanguageModel:
    if use_azure:
        if deployment_engine is None:
            raise ValueError("Deployment engine must be specified for Azure API")
        if model_kwargs is None:
            raise ValueError(
                "Azure OpenAI model kwargs must be specified for Azure API"
            )
        return AzureOpenAI(
            model=model,
            client=openai.Completion,
            deployment_name=deployment_engine,
            temperature=temperature,
            model_kwargs=model_kwargs,
            max_tokens=-1,
        )
    else:
        return OpenAI(
            temperature=temperature,
            model=model,
            client=openai.Completion,
            max_tokens=-1,
        )


def create_embedding_client(
    model: str,
    use_azure: bool = False,
    deployment_engine: Optional[str] = None,
    model_kwargs: Optional[dict] = None,
) -> Embeddings:
    if use_azure:
        if deployment_engine is None:
            raise ValueError("Deployment engine must be specified for Azure API")
        if model_kwargs is None:
            raise ValueError(
                "Azure OpenAI model kwargs must be specified for Azure API"
            )
        return OpenAIEmbeddings(
            model=model, client=openai.Embedding, deployment=deployment_engine
        )
    return OpenAIEmbeddings(model=model, client=openai.Embedding)


class BaseLLM:
    def __init__(self, model: str):
        # check whether chat API
        if model not in OPEN_AI_MODELS:
            raise ValueError(f"Invalid model {model}")

        self.model = model
        deployment_engine = None
        use_azure = False
        model_kwargs = None
        if API_TYPE == "azure":
            use_azure = True
            if model not in azure_deployment_map:
                raise ValueError(f"Please deploy {model} on Azure")
            deployment_engine = azure_deployment_map[model]
            model_kwargs = azure_openai_model_kwargs

        if model == "gpt-3.5-turbo-instruct":
            self._llm = create_completion_client(
                model,
                deployment_engine=deployment_engine,
                temperature=TEMPERATURE,
                use_azure=use_azure,
                model_kwargs=model_kwargs,
            )
        else:
            self._llm = create_chat_client(
                model,
                deployment_engine=deployment_engine,
                temperature=TEMPERATURE,
                use_azure=use_azure,
                model_kwargs=model_kwargs,
            )

    def get_llm(self):
        return self._llm

    def predict(self, prompt: str) -> str:
        return self._llm.predict(prompt)

    def chat(self, messages: List[BaseMessage]) -> BaseMessage:
        return self._llm.predict_messages(messages)


# declare llm models
OPEN_AI_MODELS_HUB = {
    "gpt-4": BaseLLM("gpt-4"),
    "gpt-3.5-turbo": BaseLLM("gpt-3.5-turbo"),
    "gpt-3.5-turbo-16k": BaseLLM("gpt-3.5-turbo-16k"),
    "gpt-3.5-turbo-instruct": BaseLLM("gpt-3.5-turbo-instruct"),
    "text-embedding-ada-002": create_embedding_client("text-embedding-ada-002")
    if API_TYPE != "azure"
    else create_embedding_client(
        "text-embedding-ada-002",
        use_azure=True,
        deployment_engine=azure_deployment_map.get("text-embedding-ada-002"),
        model_kwargs=azure_openai_model_kwargs,
    ),
}


def complete(prompt: str, model: str, system_prompt: Optional[str] = None) -> str:
    if system_prompt:
        prompt = f"{system_prompt}\n##User question\n{prompt}\n"
    if model not in OPEN_AI_MODELS_HUB:
        raise ValueError(f"Not found model {model}")
    return OPEN_AI_MODELS_HUB[model].predict(prompt)


def complete_with_messages(
    model: str,
    messages: List[Dict[str, str]],
    prompt: Optional[str] = None,
) -> str:
    chat_messages = []
    for message in messages:
        if message["role"] == "user":
            chat_messages.append(HumanMessage(content=message["content"]))
        elif message["role"] == "system":
            chat_messages.append(SystemMessage(content=message["content"]))
        else:
            chat_messages.append(
                ChatMessage(role=message["role"], content=message["content"])
            )

    if prompt is not None:
        chat_messages.append(HumanMessage(content=prompt))

    if model not in OPEN_AI_MODELS_HUB:
        raise ValueError(f"Not found model {model}")

    return OPEN_AI_MODELS_HUB[model].chat(chat_messages).content


def send_messages(messages: List[Dict[str, str]], model: str) -> str:
    return complete_with_messages(model, messages)


def chat(
    model: str, messages: List[Dict[str, str]], prompt=None
) -> List[Dict[str, str]]:
    response = complete_with_messages(model, messages, prompt)
    messages.append({"role": "assistant", "content": response})
    return messages
