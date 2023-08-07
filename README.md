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
python -m jarvis --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --replan
```


Once we have a plan, simplify it by running the command:
```bash
python -m jarvis --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose
```


Then we can run the generated instructions by executing the following commands:
```bash
python -m jarvis --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --yaml=1.yaml
python -m jarvis --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --yaml=2.yaml
```

## Run within Docker

### Build a local image
```bash
docker build -t jarvis-server:latest .
```

### Run jarvis-server
```bash
docker run --rm -p 51155:51155 \
-v $(pwd)/data:/app/data \
-v $(pwd)/workspace:/app/workspace \
-v $(pwd)/.env:/app/.env \
jarvis-server:latest
```

And so on.
