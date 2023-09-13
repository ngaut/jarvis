import yaml
import requests
import argparse
import time

def read_task_yaml(file_path):
    """
    Read and parse the yaml file.
    """
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    return data

def create_agent(task_data):
    """
    Make a POST request and return the response.
    """

    # Construct the request payload.
    payload = {
        "name": "test_cli",
        "project_id": 1,
        "description": "Jarvis serves your task",
        "goal": task_data["goal"],
        "instruction": task_data["instructions"],
        "agent_workflow": "Goal Based Workflow",
        "constraints": [
            "If you are unsure how you previously did something or want to recall past events, thinking about similar events will help you remember.",
            "Ensure the tool and args are as per current plan and reasoning",
            "Exclusively use the tools listed under \"TOOLS\"",
            "REMEMBER to format your response as JSON, using double quotes (\"\") around keys and string values, and commas (,) to separate items in arrays and objects. IMPORTANTLY, to use a JSON object as a string in another JSON object, you need to escape the double quotes."
        ],
        "toolkits": [],
        "tools": [37],
        "exit": "No exit criterion",
        "iteration_interval": 500,
        "model": "gpt-4",
        "max_iterations": 25,
        "permission_type": "God Mode",
        "LTM_DB": "Pinecone",
        "user_timezone": "Asia/Shanghai",
        "knowledge": None
    }
    response = requests.post("http://localhost:3000/api/agents/create", json=payload)
    return response.json()

def create_run(agent_id, goal, instruction):
    """
    Create a new run.
    """
    payload = {
        "agent_id": agent_id,
        "name": "New Run",
        "goal": goal,
        "instruction": instruction
    }
    
    response = requests.post("http://localhost:3000/api/agentexecutions/add", json=payload)
    return response.json()

def get_run_status(execution_id):
    """
    Fetch the run status.
    """
    response = requests.get(f"http://localhost:3000/api/agentexecutionfeeds/get/execution/{execution_id}")
    return response.json()

def pause_run(execution_id):
    """
    Update the status of a specific run.
    
    Parameters:
        - execution_id (int): The ID of the run to be updated.

    Returns:
        - response (dict): The response from the API call.
    """
    url = f"http://localhost:3000/api/agentexecutions/update/{execution_id}"
    payload = {"status": "PAUSED"}
    
    response = requests.put(url, json=payload)
    
    return response.json()

def get_agent_executions(agent_id):
    """
    Sends a GET request to retrieve the execution details of a specified agent.

    Parameters:
        - agent_id (int): The ID of the agent.

    Returns:
        - list: A list of dictionaries containing execution details.
    """
    url = f"http://localhost:3000/api/agentexecutions/get/agent/{agent_id}"
    
    # Send the GET request
    response = requests.get(url)
    
    # Raise an exception if the request was unsuccessful
    response.raise_for_status()
    
    return response.json()

def print_run(agent_id, execution_id, feed):
    """
    Pretty print the role and feed from the provided data.

    Parameters:
        - agent_id (int): The ID of the agent.
        - execution_id (int): The ID of the execution.
        - feed (dict): The feed data containing role and content.

    Returns:
        None. This function prints the information directly.
    """
    role = feed.get('role', 'Unknown Role')
    feed_content = feed.get('feed', 'No Feed Content')
    
    # Create a divider
    divider = "-" * 40

    # Print the details
    print(f"Agent ID: {agent_id}")
    print(f"Execution ID: {execution_id}")
    print(divider)
    print(f"Role: {role}")
    print(divider)
    print("Feed:")
    print(feed_content)
    print(divider + "\n")

def main():
    # Argument parser for CLI
    parser = argparse.ArgumentParser(description='CLI tool for processing task from yaml')
    parser.add_argument('--task', type=str, required=True, help='Path to the task.yaml file')
    args = parser.parse_args()

    # Read and parse task.yaml
    task_data = read_task_yaml(args.task)
    goal = task_data['goal']
    instructions = task_data['instructions']

    # Make the POST request to create a agent for this task
    agent_config = create_agent(task_data)
    # agent_config = {'id': 12, 'execution_id': 116, 'name': 'test_cli', 'contentType': 'Agents'}
    agent_id = agent_config['id']
    print(f"Agent {agent_id} created")
    # wait for agent scheduled
    time.sleep(10)

    execution_id = None
    executions = get_agent_executions(agent_id)
    for execution in executions:
        if execution['status'] == 'RUNNING':
            execution_id = execution['id']
            break
        elif execution['status'] == 'CREATED':
            pause_response =  pause_run(execution_id)
            print(f"Pause execution {execution_id} that is not scheduled. Response={pause_response}")
    
    if execution_id is None:
        # Create a new run
        run_response = create_run(agent_id, goal, instructions)
        print(f"Run {run_response['id']} created")
        execution_id = run_response['id']

    feed_index = 0
    while True:
        # check if the run is scheduled
        run_status = get_run_status(execution_id)
        feeds = run_status['feeds']
        for i in range(feed_index, len(feeds)):
            print_run(agent_id, execution_id, feeds[i])
        feed_index = len(feeds)

        if run_status['status'] == 'PAUSED' or run_status['status'] == 'COMPLETED':
            action = input(f"Execution {execution_id} is {run_status['status']}, Choose action [exit, instruct]:")
            if action == "exit":
                break
            elif action == "instruct":
                # Allow the user to add instructions
                new_instruction = input("Add new instructions (separate multiple goals with '|'): ").split("|")
                instructions.extend(new_instruction)
                
                # Create a new run with updated goals and instructions
                run_response = create_run(agent_id, goal, instructions)
                execution_id = run_response['id']
                feed_index = 0
        time.sleep(5)

if __name__ == "__main__":
    main()
