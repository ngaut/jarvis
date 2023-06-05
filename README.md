# jarvis: A simple autonomous GPT-4 runner

[![](https://dcbadge.vercel.app/api/server/98KeRysd?style=flat)](https://discord.gg/98KeRysd)
[![Twitter Follow](https://img.shields.io/twitter/follow/rokstrnisa?style=social)](https://twitter.com/intent/follow?screen_name=rokstrnisa)
## A virtual machine designed for AI

## Setup

-   Install [`pipenv`](https://pypi.org/project/pipenv/).
-   Clone this repo and change directory to it.
-   Run `pipenv shell` to enter the Python virtual environment and `pipenv install` to install the dependencies.
-   Rename `.env.template` to `.env` and fill in your [`OPENAI_API_KEY`](https://platform.openai.com/account/api-keys),
    and optionally [`ELEVEN_LABS_API_KEY`](https://elevenlabs.io) (for speech).

## Usage

Run `python smartgpt/main.py --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose` to start the program.

