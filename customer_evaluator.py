import language_tool_python
import openai
import yaml
import re
from typing import Optional, Any, Dict

from langsmith import RunEvaluator
from langchain.evaluation.schema import StringEvaluator
from langsmith.evaluation import EvaluationResult

from langchain.chains import LLMChain
from langchain.chat_models import ChatOpenAI

from jarvis.smartgpt import gpt


class GrammarAccuracyEvaluator(StringEvaluator):
    def _evaluate_strings(
            self,
            *,
            prediction: str,
            reference: Optional[str] = None,
            input: Optional[str] = None,
            **kwargs: Any,
    ) -> Dict[str, Any]:
        tool = language_tool_python.LanguageTool('en-US')
        matches = tool.check(prediction)
        grammar_errors = len(matches)
        score = max(0, 1 - grammar_errors / len(prediction.split()))
        return {
            'score': score,
            'value': prediction,
            'reasoning': f'The prediction has {grammar_errors} grammar errors.',
        }


class YAMLCorrectnessEvaluator(StringEvaluator):
    def _evaluate_strings(
            self,
            *,
            prediction: str,
            reference: Optional[str] = None,
            input: Optional[str] = None,
            **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            yaml.safe_load(prediction)
            score = 1.0
            reasoning = 'The prediction is a valid YAML format.'
        except yaml.YAMLError as e:
            score = 0.0
            reasoning = str(e)
        return {
            'score': score,
            'value': prediction,
            'reasoning': reasoning,
        }


class InstructionValidityEvaluator(RunEvaluator):
    def __init__(self):
        if gpt.API_TYPE == "azure":
            llm = ChatOpenAI(
                client=openai.ChatCompletion,
                temperature=0.0,
                model_kwargs={
                    "engine": gpt.GPT_4,
                },
            )
        else:
            llm = ChatOpenAI(
                temperature=0.0,
                model=gpt.GPT_4,
                client=openai.ChatCompletion,
            )

        template = """
        Here are a set of instructions:
        --------
        {instructions}
        --------
        On a scale from 0 to 100, how valid and complete do these instructions appear? Provide a score at the end.
        """
        self.eval_chain = LLMChain.from_string(llm=llm, template=template)

    def evaluate_run(
            self, run: dict, example: Optional[dict] = None
    ) -> EvaluationResult:
        if "instructions" not in run:
            return EvaluationResult(key="InstructionValidity", score=0, details="Instructions missing from run")

        instruction_str = "\n".join([str(instruction) for instruction in run["instructions"]])

        evaluator_result = self.eval_chain(dict(instructions=instruction_str))

        score = re.search(r"\d+", evaluator_result["text"]).group(0)
        if score is not None:
            score = float(score.strip()) / 100.0

        return EvaluationResult(key="InstructionValidity", score=score)
