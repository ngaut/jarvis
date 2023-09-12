import re
import yaml
import openai
from typing import Optional, Any, Dict

from langsmith import RunEvaluator
from langchain.evaluation.schema import StringEvaluator
from langsmith.evaluation import EvaluationResult

from langchain.chains import LLMChain
from langchain.chat_models import ChatOpenAI

from jarvis.smartgpt import gpt
from jarvis.smartgpt import instruction


class GrammarAccuracyEvaluator(StringEvaluator):
    def _check_jvm_syntax(self, prediction: str) -> bool:
        # Checking for valid jvm.eval and jvm.get calls
        eval_pattern = re.compile(r'jvm\.eval\([^)]+\)')
        get_pattern = re.compile(r'jvm\.get\([^)]+\)')

        if not all([bool(re.fullmatch(eval_pattern, s)) for s in re.findall(r'jvm\.eval\([^)]+\)', prediction)]):
            return False
        if not all([bool(re.fullmatch(get_pattern, s)) for s in re.findall(r'jvm\.get\([^)]+\)', prediction)]):
            return False

        # Add more checks for other syntax rules if needed
        return True

    def _evaluate_strings(
            self,
            *,
            prediction: str,
            reference: Optional[str] = None,
            input: Optional[str] = None,
            **kwargs: Any,
    ) -> Dict[str, Any]:

        if self._check_jvm_syntax(prediction):
            return {
                'score': 1.0,
                'value': prediction,
                'reasoning': 'The prediction follows the correct JVM syntax.',
            }
        else:
            return {
                'score': 0.0,
                'value': prediction,
                'reasoning': 'The prediction does not follow the correct JVM syntax.',
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

    def evaluate_run(self, run: dict, example: Optional[dict] = None) -> EvaluationResult:
        # 首先，检查run中的必要字段
        if "instructions" not in run or "task" not in run:
            return EvaluationResult(key="InstructionValidity", score=0, details="Instructions or task missing from run")

        # 检查 start_seq 是否合法
        start_seq = run.get("start_seq", -1)
        if start_seq < 0 or start_seq >= len(run["instructions"]):
            return EvaluationResult(key="InstructionValidity", score=0,
                                    details=f"Invalid start sequence number: {start_seq}")

        execution_result = None
        # 尝试执行指令
        try:
            interpreter = instruction.JVMInterpreter()
            execution_result = interpreter.run(run["instructions"], task=run["task"])
        except Exception as e:
            # 如果指令执行失败，则返回评分为0
            return EvaluationResult(key="InstructionValidity", score=0, details=str(e))

        # 如果指令执行成功，将执行结果传给AI进行评估
        evaluator_result = self.eval_chain(dict(instructions=execution_result))

        # # 如果指令执行成功，则将指令转换为字符串，并使用AI评估
        # instruction_str = "\n".join([str(instruction) for instruction in run["instructions"]])
        # evaluator_result = self.eval_chain(dict(instructions=instruction_str))

        # 从AI的评估结果中提取得分
        score = re.search(r"\d+", evaluator_result["text"]).group(0)
        if score is not None:
            score = float(score.strip()) / 100.0
        else:
            score = 0

        return EvaluationResult(key="InstructionValidity", score=score)
