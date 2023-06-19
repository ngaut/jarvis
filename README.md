# jarvis: A virtual machine designed for AI


## Setup

-   Install [`pipenv`](https://pypi.org/project/pipenv/).
-   Clone this repo and change directory to it.
-   Run `pipenv shell` to enter the Python virtual environment and `pipenv install` to install the dependencies.
-   Rename `.env.template` to `.env` and fill in your [`OPENAI_API_KEY`](https://platform.openai.com/account/api-keys),
    and optionally [`ELEVEN_LABS_API_KEY`](https://elevenlabs.io) (for speech).

## Usage

Run `python smartgpt/main.py --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --replan` to start the program.
Once we got a plan, simplify Run `python smartgpt/main.py --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --replan` to generate instructions.
Then we can run those instructions: 
python smartgpt/main.py --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --json=1.json
python smartgpt/main.py --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --json=2.json
and so on.


