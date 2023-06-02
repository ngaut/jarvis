from typing import Optional
from dotenv import load_dotenv
import time, logging
import gpt


def gen_instructions(model: str):
    #input the goal
    goal = input("Please input your goal: ")

    try:
        logging.info("========================")
        prompt = (
            f"our goal: {goal}\n\n"
            "your json response:```json"
        )
        resp = gpt.complete_with_system_message(prompt, model=model)
        logging.info("Response from AI: %s", resp)
        return resp

    except Exception as err:
        logging.error("Error in main: %s", err)
        time.sleep(1)

