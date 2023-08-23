from __future__ import annotations
from pydantic import Extra
from typing import Any, Dict, List, Optional
import os

from langsmith import Client
from langchain.smith import RunEvalConfig, run_on_dataset
from jarvis.smartgpt.translator import Translator
from jarvis.smartgpt import gpt
from jarvis.smartgpt import initializer


from langchain.callbacks.manager import (
    AsyncCallbackManagerForChainRun,
    CallbackManagerForChainRun,
)
from langchain.chains.base import Chain


initializer.setup()
workspace_dir = "workspace/evaluation"
os.makedirs(workspace_dir, exist_ok=True)
os.chdir(workspace_dir)


class TranslatorChain(Chain):
    """
    An example of a custom chain.
    """

    output_key: str = "output"  #: :meta private:
    jarvis_translator = Translator(gpt.GPT_4)

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True

    @property
    def input_keys(self) -> List[str]:
        return ["task_info"]

    @property
    def output_keys(self) -> List[str]:
        return [self.output_key]

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        result = tx.translate_to_instructions(**inputs)
        return {self.output_key: result}

    async def _acall(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        result = tx.translate_to_instructions(**inputs)
        return {self.output_key: result}

    @property
    def _chain_type(self) -> str:
        return "my_custom_chain"


def chain_constructor():
    return TranslatorChain()


client = Client()
eval_config = RunEvalConfig(
    evaluators=["qa"],
)
chain_results = run_on_dataset(
    client,
    dataset_name="jarvis-translator",
    llm_or_chain_factory=chain_constructor,
    concurrency_level=1,
    evaluation=eval_config,
)
