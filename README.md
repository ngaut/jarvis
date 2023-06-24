# jarvis: A virtual machine designed for AI

## Setup

- Install [`pipenv`](https://pypi.org/project/pipenv/).
- Clone this repo and change directory to it.
- Run `pipenv shell` to enter the Python virtual environment and `pipenv install` to install the dependencies.
- Rename `.env.template` to `.env` and fill in your [`OPENAI_API_KEY`](https://platform.openai.com/account/api-keys),
  and optionally [`ELEVEN_LABS_API_KEY`](https://elevenlabs.io) (for speech).
- Configure `GOOGLE_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID` environment variables in your .env file.
- Please add the absolute path of the project directory to your PYTHONPATH environment variable and set it in your .env file

## Usage

Run the following command to start the program:

```bash
python main.py --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --replan
```


Once we have a plan, simplify it by running the command:
```bash
python main.py --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --replan
```


Then we can run the generated instructions by executing the following commands:
```bash
python main.py --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --json=1.json
python main.py --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --json=2.json
```


And so on.
