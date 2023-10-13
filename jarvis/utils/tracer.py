import os

from langsmith.run_helpers import traceable


def conditional_chan_traceable(run_type: str):
    def decorator(func):
        if os.environ.get("LANGCHAIN_TRACING_V2", "false").lower() == "true":
            return traceable(run_type=run_type)(func)
        return func

    return decorator
