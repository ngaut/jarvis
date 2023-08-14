import logging
import os
import json

from jarvis.extensions.jarvis_agent import JarvisAgent

# Logging file name and line number
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)

os.chdir("/Users/ianz/Work/jarvis/workspace")
agent = JarvisAgent()
info = agent.execute_with_plan("tell me what's tidb", subdir="test", skip_gen=True)
print(info.json())