import os
import sys
import argparse
import logging

import yaml
from dotenv import load_dotenv

from smartgpt import actions
from smartgpt import planner
from smartgpt import gpt
from smartgpt import jvm
from smartgpt import instruction


BASE_MODEL = gpt.GPT_4

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to the configuration file')
    parser.add_argument('--timeout', type=int, default=1, help='Timeout for user input')
    parser.add_argument('--continuous', action='store_true', help='Continuous mode')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--replan', action='store_true', help='create a new plan')
    parser.add_argument('--yaml', type=str, help='Path to the yaml file to execute plan from')
    parser.add_argument('--startseq', type=int, default=0, help='Starting sequence number')

    args = parser.parse_args()

    load_dotenv()

    # Load configuration from YAML file
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # Logging file name and line number
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        stream=sys.stdout
    )

    print("Welcome to Jarvis, your personal assistant for everyday tasks!\n")

    assistant_config = config.get('assistant', {})
    args.timeout = args.timeout or assistant_config.get('timeout', 30)
    args.verbose = args.verbose or assistant_config.get('verbose', False)
    args.continuous = args.continuous or assistant_config.get('continuous', False)
    args.replan = args.replan or assistant_config.get('replan', False)

    os.makedirs("workspace", exist_ok=True)
    os.chdir("workspace")

    jvm.load_kv_store()
    actions.load_cache()

    # If a YAML file path is provided, load the plan_with_instrs from the YAML file, otherwise generate a new plan_with_instrs
    if args.yaml:
        # Load the plan_with_instrs from the YAML file
        with open(args.yaml, 'r') as f:
            plan_with_instrs = yaml.safe_load(f)
    else:
        # Generate a new plan
        planner.gen_instructions(BASE_MODEL, replan=args.replan)
        exit(0)

    # Find the starting sequence number
    start_seq = args.startseq
    logging.info(f"plan_with_instrs: {plan_with_instrs['instructions']}")

    # Make sure start_seq is within bounds
    if start_seq < 0 or start_seq >= len(plan_with_instrs["instructions"]):
        print(f"Invalid start sequence number: {start_seq}")
        exit(1)

    # Run the instructions starting from start_seq
    logging.info(f"Running instructions from  {plan_with_instrs['instructions'][start_seq]}\n")

    interpreter = instruction.JVMInterpreter()
    interpreter.run(plan_with_instrs["instructions"][start_seq:], task=plan_with_instrs["task"])
