from __future__ import annotations
from pydantic import Extra
from typing import Any, Dict, List, Optional
import os

from langsmith import Client
from langchain.smith import RunEvalConfig, run_on_dataset
from jarvis.smartgpt.translator import Translator
from jarvis.smartgpt import gpt
from jarvis.smartgpt import initializer
from langchain.prompts.prompt import PromptTemplate


from langchain.callbacks.manager import (
    AsyncCallbackManagerForChainRun,
    CallbackManagerForChainRun,
)
from langchain.chains.base import Chain


initializer.setup()
workspace_dir = "workspace/evaluation"
os.makedirs(workspace_dir, exist_ok=True)
os.chdir(workspace_dir)


class TranslatorMockChain(Chain):
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
        result = self.jarvis_translator.translate_to_instructions(**inputs)
        return {self.output_key: result}

    async def _acall(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        result = self.jarvis_translator.translate_to_instructions(**inputs)
        return {self.output_key: result}

    @property
    def _chain_type(self) -> str:
        return "my_custom_chain"


template = """You are a teacher grading a quiz.
You are given a question, the student's answer, and the true answer, and are asked to score the student answer as either CORRECT or INCORRECT.

Example Format:
QUESTION: question here
STUDENT ANSWER: student's answer here
TRUE ANSWER: true answer here
GRADE: CORRECT or INCORRECT here

You need to know:
1. The '<to_fill>' in instructions is a placeholder that will be replaced during execution.
2. The types of instructions are in the range: 'WebSearch', 'FetchWebContent', 'TextCompletion', 'If', 'Loop', 'RunPython'. And the arguments of each instruction are predefined.
3. 'jvm.get()' MUST be wrapped in 'jvm.eval()', good examples like: "jvm.eval(jvm.get('story_urls.seq1.list')[jvm.get('idx')])", "jvm.eval(len(jvm.list_keys_with_prefix('MetaGPT_content_')))".
4. 'TextCompletion' has a powerful LLM backend which is also good at extracting information from web pages.

Grade the student answers based ONLY on their factual accuracy. Ignore differences in punctuation and phrasing between the student answer and true answer. It is OK if the student answer contains more information than the true answer, as long as it does not contain any conflicting statements. Begin! 

QUESTION: {query}
STUDENT ANSWER: {result}
TRUE ANSWER: {answer}
GRADE:"""
PROMPT = PromptTemplate(
    input_variables=["query", "result", "answer"], template=template
)

eval_config = RunEvalConfig(
    evaluators=[
        RunEvalConfig.QA(prompt=PROMPT),
        "cot_qa",
    ]
)
client = Client()
chain_results = run_on_dataset(
    client,
    dataset_name="jarvis-translator",
    llm_or_chain_factory=lambda: TranslatorMockChain(),
    concurrency_level=1,
    evaluation=eval_config,
)
