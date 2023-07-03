from typing import Any
from smartgpt.planner import GEN_PLAN__SYS_PROMPT

prompt=GEN_PLAN__SYS_PROMPT

class SmartAgent:
    @property
    def name(self):
        return "smart_agent"

    @property
    def description(self):
        return "Jarvis, as a smart AI agent, I can accept complex task goals, break them down into multiple simple tasks to execute and output results."

    def __call__(self, task: str, context: str, **kargs: Any) -> str:
        raise NotImplementedError("TODO: implement agent")