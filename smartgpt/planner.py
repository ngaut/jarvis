from typing import Optional
from dotenv import load_dotenv
from spinner import Spinner
import actions, gpt
import os, sys, time, re, signal, argparse, logging
import ruamel.yaml as yaml
from datetime import datetime


def gen_instructions(model: str):
    #input the goal
    goal = input("Please input your goal: ")

    try:
        logging.info("========================")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt = (
            f"## Current time: {current_time}\n"
            f"our goal: {goal}."
            "your json response:```json"
        )
        resp = gpt.complete_with_system_message(prompt, model=model)
        logging.info("Response from AI: %s", resp)
        return resp

    except Exception as err:
        logging.error("Error in main: %s", err)
        time.sleep(1)

