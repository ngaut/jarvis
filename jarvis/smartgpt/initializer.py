from dotenv import load_dotenv

from jarvis.smartgpt.preprompts import init as init_prompts
from jarvis.smartgpt.fewshot import init as init_examples

# Load the users .env file into environment variables
load_dotenv(verbose=True, override=True)
del load_dotenv


def setup():
    init_prompts()
    init_examples()
