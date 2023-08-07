# Jarvis: A Virtual Machine Tailored for AI

Jarvis is a virtual machine designed to seamlessly integrate and run AI models. This README provides a step-by-step guide to setting up and using Jarvis.

## Prerequisites

1. Ensure [pipenv](https://pypi.org/project/pipenv/) is installed on your system.
2. Obtain the necessary API keys to interface with third-party services:
- [OPENAI_API_KEY](https://platform.openai.com/account/api-keys)
- Both `GOOGLE_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID`` for integrating Google Search Engine.

## Setup

1. Clone this repository:
```
git clone https://github.com/ngaut/jarvis.git && cd jarvis
```

2. Initiate a Python virtual environment:
```
pipenv shell
```

3. Install the dependencies:
```
pipenv install
```

4. Set up the environment variables:
- Rename `.env.template` to `.env`, and input the necessary API keys mentioned in the Prerequisites section.
- Update the `PYTHONPATH` environment variable with the absolute path of this project and include it in your .env file.


## Usage

To generate a plan for tasks execution based on input goals:

```
python -m jarvis --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --replan
```

To generate a plan for tasks execution based on a given goal file, which should be placed in the 'workspace' directory:

```
python -m jarvis --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --replan --goalfile=<GOALFILE>
```

To translate all tasks in plan into JVM instructions:

```
python -m jarvis --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose
```

To translate a task with specified task number into JVM instructions:

```
python -m jarvis --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --compile=<task_num>
```

To execute JVM instructions in the specified task:

```
python -m jarvis --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --yaml=1.yaml
python -m jarvis --continuous --timeout 3 --config=./config.yaml --startseq=0 --verbose --yaml=2.yaml
```

## Docker Integration

Run Jarvis within a Docker container by following these steps:

### Build a Local Docker Image

```
docker build -t jarvis-server:latest .
```

Or pull a pre-built Docker image

```
docker pull public.ecr.aws/l7n5d1m0/jarvis-server:latest
```

### Running Jarvis Server

The Jarvis server operates on port `51155` by default, offering services via the gRPC protocol.

To run the Jarvis server with Docker:

```
docker run --rm -p 51155:51155 \
-v $(pwd)/workspace:/app/workspace \
-v $(pwd)/.env:/app/.env \
jarvis-server:latest
```

Note: Ensure you've configured the `.env` file in the current directory before proceeding.

## Working with SuperAGI

SuperAGI is an open-source autonomous AI framework to enable you to develop and deploy
useful autonomous agents quickly & reliably.

Here are instructions on how to integrate Jarvis into SuperAGI:

1. Clone the SuperAGI repository, but do not clone it within the Jarvis' project directory.

```
git clone https://github.com/TransformerOptimus/SuperAGI.git
```

2. Follow the instructions to complete the setup for SuperAGI:
https://github.com/TransformerOptimus/SuperAGI#%EF%B8%8F-setting-up

Note: Provide the OpenAI API Key in config.yaml at least, other items are optional.

3. Run SuperAGI by executing `docker-compose up --build`, it will take some time.

4. Open your browser and navigate to http://localhost:3000 to access SuperAGI.

5. Important: Click the gear icon in the upper right corner of the UI interface to enter the 'settings' tab page and set the OpenAI API Key again, save it.

6. Add Jarvis as a tool: Click the '+Add Tool' button under Toolkits, and type: 'https://github.com/IANTHEREAL/jarvis' in the input box on the tab page, click 'Add tool' button.

7. Important: Restart docker-compose first, so that you can find the Jarvis toolkit loaded in the tool list.

8. Make sure Jarvis Server's Docker is running.

9. Configure Jarvis Tookit: Choose Jarvis Toolkit in the tool list, and type in the 'Jarvisaddr' input box as: 'host.docker.internal:51155', save it.

10. So far, you can create a new agent to perform some task goals, note: Jarvis should be included in Tools box.
