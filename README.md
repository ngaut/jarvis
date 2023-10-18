# Jarvis: AI-Powered Virtual Machine

Welcome to Jarvis, a cutting-edge virtual machine designed specifically to facilitate AI tasks. This README offers a comprehensive guide to effectively set up and utilize Jarvis for optimal results.

## Demo

Jarvis collaborates with Microsoft's AutoGen to do tweet analysis.

[Demo](https://github.com/ngaut/jarvis/assets/10701973/d75d4314-d1d8-41d2-879d-bd6cb678f596)

## Prerequisites

1. Obtain the necessary API keys to interface with third-party services:
- [OPENAI_API_KEY](https://platform.openai.com/account/api-keys)
- Both `GOOGLE_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID` for integrating Google Search Engine.

## Installation and Setup

1. Clone this repository:

```
git clone https://github.com/ngaut/jarvis.git && cd jarvis
```

2. Set up the environment variables:

- Rename `.env.template` to `.env`, and input the necessary API keys mentioned in the Prerequisites section.

3. Build a Local Docker Image

```
docker build -t jarvis-server:latest .
```

4. Running Jarvis Server

The Jarvis server operates on port `51155` by default, offering services via the gRPC protocol.

To run the Jarvis server with Docker:

```
docker run --rm -p 51155:51155 \
-v $(pwd)/workspace:/app/workspace \
-v $(pwd)/.env:/app/.env \
jarvis-server:latest
```

Note: Ensure you've configured the `.env` file in the current directory before proceeding.

## Usage

For guidance, you can refer to the code provided in this [demo](example.ipynb)

1. Develop a Skill:

Develop a skill that generates summaries of top stories from Hacknews.

```python
stub.Execute(
    jarvis_pb2.ExecuteRequest(
        task=(
            "Collect the top three articles featured on Hacker News (https://news.ycombinator.com/), "
            "and produce a single professional reading summary that encompasses the content of all three articles, formatted in a user-friendly manner."
        )
    )
)
```

Task output example:

```
executor_id: "ea8fcfdf59c011002875a88fcdac5e97"
task_id: 1
task: Collect the top three articles featured on Hacker News (https://news.ycombinator.com/), and produce a single professional reading summary that encompasses the content of all three articles, formatted in a user-friendly manner.
result: "The University of Turku in Finland is developing an artificial language corpus proficient in all European languages ..."
```

2. Save a Skill:

A step-by-step guide to save a developed skill for subsequent use.

```python
stub.SaveSkill(
    jarvis_pb2.SaveSkillRequest(
        executor_id="ea8fcfdf59c011002875a88fcdac5e97",
        skill_name="HackerNews top three articles summary",
    )
)
```

Task output example:

```
executor_id: "ea8fcfdf59c011002875a88fcdac5e97"
result: "skill is saved as HackerNews top three articles summary"
```


3. Reuse Skills:

Recall and utilize previously saved skills for the same or related tasks.

```python
python run_skill_chain.py --workspace=workspace --skill_dir=skill_library --execution_dir=summary_hn_news --skills="HackerNews top three articles summary"
```

Task output example:

```
executing skill: HackerNews top three articles summary
--------------------------------------------------
Skill Execution Summary
--------------------------------------------------

Skill Result: The article discusses a 3 state, 3 symbol Turing Machine called 'Bigfoot' that cannot be proven to halt or not without solving a Collatz-like problem ...
Skill Error:  None

==================================================
Detailed Task Infos
==================================================

Subtask: Collect the top three articles featured on Hacker News (https://news.ycombinator.com/), and produce a single professional reading summary that encompasses the content of all three articles, formatted in a user-friendly manner.
Result: ...
Error:   None

--------------------------------------------------

End of Execution Summary
--------------------------------------------------
```
