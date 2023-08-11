import json
import os
import random
import time
from copy import deepcopy
from abc import ABC, abstractmethod
import openai


from tenacity import retry, wait_random_exponential, stop_after_attempt
from termcolor import colored

FORMAT_INSTRUCTIONS_SYSTEM_FUNCTION = """You are AutoGPT, you can use many tools(functions) to do the following task.
First I will give you the task description, and your task start.
At each step, you need to give your thought to analyze the status now and what to do next, with a function call to actually excute your step.
After the call, you will get the call result, and you are now in a new state.
Then you will analyze your status now, then decide what to do next...
After many (Thought-call) pairs, you finally perform the task, then you can give your finial answer.
Remember: 
1.the state change is irreversible, you can't go back to one of the former state, if you want to restart the task, say "I give up and restart".
2.All the thought is short, at most in 5 sentence.
3.You can do more then one trys, so if your plan is to continusly try some conditions, you can do one of the conditions per try.
Let's Begin!
Task description: You should use functions to help handle the real time user querys. 
Remember:
1.ALWAYS call "Finish" function at the end of the task. And the final answer should contain enough information to show to the user,If you can't handle the task, or you find that function calls always fail(the function is not valid now), use function Finish->give_up.

You have access of the following tools:
{tool_description}
"""

FORMAT_INSTRUCTIONS_USER_FUNCTION = """
{input_description}
Begin!
"""

DIVERSITY_PROMPT = """This is not the first time you try this task, all previous trails failed.
Before you generate my thought for this state, I will first show you your previous actions for this state, and then you must generate actions that is different from all of them. Here are some previous actions candidates:
{previous_candidate}
Remember you are now in the intermediate state of a trail, you will first analyze the now state and previous action candidates, then make actions that is different from all the previous."""


LLM_PAIRWISE_RANK_SUBFIX_SYSTEM_PROMPT = """
You are value-GPT, which is an expert of defining which trail is better, which trail is more close to solving the task. 
All candidate tries to solve this task with some funciton calls:
*******************************
{{TASK_DESCRIPTION}}
You should use functions to help handle the real time user querys. 
Remember:
1.ALWAYS call "Finish" function at the end of the task. And the final answer should contain enough information to show to the user,If you can't handle the task, or you find that function calls always fail(the function is not valid now), use function Finish->give_up.

You have access of the following tools:
{tool_description}
{{END_TASK_DESCRIPTION}}
*******************************
First, all candidate do the following things:
{intersect_trice}
After that, there are two candidates A and B, they do different things:
*******************************
{{CANDIDATE_A_START}}
{candidate_A}
{{CANDIDATE_A_END}}
*******************************
{{CANDIDATE_B_START}}
{candidate_B}
{{CANDIDATE_B_END}}
Which try do you think is more helpful to solving the task?
"""

LLM_PAIRWISE_RANK_USER_PROMPT = """
Tell me which candidate is better in ONE Word: "A" or "B":"""


def rank2symmetry(llm, llm_rank_args, cand1, cand2):
    """
    Use llm to compare the height, due to the sequence, you need to compare each of the two in the front
    """
    single_rank_func = llm_rank_args["rank_func"]
    score = [0, 0]
    bigger1, query_count1, total_tokens1 = single_rank_func(
        llm, llm_rank_args, cand1, cand2
    )
    score[1 - bigger1] += 1
    bigger2, query_count2, total_tokens2 = single_rank_func(
        llm, llm_rank_args, cand2, cand1
    )
    score[bigger2] += 1
    if score[0] > score[1]:
        return 1, query_count1 + query_count2, total_tokens1 + total_tokens2
    elif score[0] < score[1]:
        return -1, query_count1 + query_count2, total_tokens1 + total_tokens2
    else:
        return 0, query_count1 + query_count2, total_tokens1 + total_tokens2


def rank2_subfix(llm, llm_rank_args, cand1, cand2):
    """
    Assumed that the two candidates have a long common prefix
    """
    anscestor_interesction = TreeNode.find_ancestor_intersection(cand1, cand2)
    assert anscestor_interesction is not None
    intersect_trice = anscestor_interesction.get_former_trice_from_this_node(
        end_node=None
    )
    trice_1 = cand1.get_former_trice_from_this_node(end_node=anscestor_interesction)
    trice_2 = cand2.get_former_trice_from_this_node(end_node=anscestor_interesction)

    system_message = LLM_PAIRWISE_RANK_SUBFIX_SYSTEM_PROMPT
    system_message = system_message.replace(
        "{tool_description}", llm_rank_args["tool_descriptions"]
    )
    system_message = system_message.replace("{intersect_trice}", intersect_trice)
    system_message = system_message.replace("{candidate_A}", trice_1)
    system_message = system_message.replace("{candidate_B}", trice_2)
    llm.change_messages(
        [
            {"role": "system", "content": system_message},
            {"role": "user", "content": LLM_PAIRWISE_RANK_USER_PROMPT},
        ]
    )
    output, total_tokens = llm.parse([])
    if output["content"].strip().lower()[-1] == "a":
        return 1, 1, total_tokens
    else:
        return 0, 1, total_tokens


def sum_based_rankn(llm, llm_rank_args, candidates):
    """
    All pairs are sorted pairwise, sum the total points, and choose the best
    """
    total_querys = 0
    total_tokens = 0
    scores = [0.0] * len(candidates)
    for i in range(len(candidates) - 1):
        for j in range(i + 1, len(candidates)):
            pairwise_rank, query_count, rank2_tokens = rank2symmetry(
                llm, llm_rank_args, candidates[i], candidates[j]
            )
            total_querys += query_count
            total_tokens += rank2_tokens
            if pairwise_rank > 0:
                scores[i] += 1.0
            elif pairwise_rank < 0:
                scores[j] += 1.0
            else:
                scores[i] += 0.5
                scores[j] += 0.5
    return scores, total_querys, total_tokens

class Tool(ABC):
    def __init__(self, name, description):
        self.name = name
        self.description = description

    def get_description(self):
        return self.description

    def get_name(self):
        return self.name

    @abstractmethod
    def get_function_calling(self):
        pass

    @abstractmethod
    def execute(self, function_args):
        pass

class FinishTool(Tool):
    def __init__(self):
        super().__init__(
            name="Finish",
            description=("If you believe that you have obtained a result that can answer the task, please call this function "
                         "to provide the final answer. Alternatively, if you recognize that you are unable to proceed with "
                         "the task in the current state, call this function to restart. Remember: you must ALWAYS call this "
                         "function at the end of your attempt, and the only part that will be shown to the user is the final "
                         "answer, so it should contain sufficient information.")
        )

    def execute(self, function_args):
        return_type = function_args.get("return_type")
        final_answer = function_args.get("final_answer", "The current reasoning path cannot lead to a valid answer")
        if return_type == "give_answer":
            return (final_answer, 1)
        elif return_type == "give_up":
            return (final_answer, 2)
        else:
            return ("ivalid required argument for return_type, only give_answer and give_up are allowed", 3)
    
    def get_function_calling(self):
        return {
            "name": self.get_name(),
            "description": self.get_description(),
            "parameters": {
                "type": "object",
                "properties": {
                    "return_type": {
                    "type": "string",
                    "enum": ["give_answer", "give_up"],
                },
                "final_answer": {
                    "type": "string",
                    "description": 'The final answer you want to give the user. You should have this field if "return_type"=="give_answer"',
                },
                },
                "required": ["return_type"],
                "optional": [],
            }
        }  

class TextCompletionTool(Tool):
    def __init__(self):
        super().__init__(
            name="text_completion",
            description= "Generate human-like text based on user questions",
        )

    def execute(self, function_args):
        question = function_args.get("text", None)
        if question is None:
            return ("invalid required argument for question", 3)
        
        response = openai.ChatCompletion.create(
            model= "gpt-3.5-turbo-16k-0613",
            messages= [{"role": "user", "content": question}],
            request_timeout=60,
        )

        choices = response["choices"]  # type: ignore
        completion = choices[0].message.content.strip()
        return (completion, 0)

    
    def get_function_calling(self):
        return {
            "name": self.get_name(),
            "description": self.get_description(),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": 'please fille the text for text_completion',
                    },
                },
                "required": ["text"],
                "optional": [],
            }
        }

class Executor:
    def __init__(self, tools: list[Tool]):
        self.tools = tools

    def get_tools_descriptions(self):
        descriptions = []
        for tool in self.tools:
            descriptions.append([tool.get_name(), tool.get_description()])
        return json.dumps(descriptions)

    def get_tools_function(self):
        functions = []
        for tool in self.tools:
            functions.append(tool.get_function_calling())
        return functions

    def step(self, function_name, function_args):
        for tool in self.tools:
            if tool.get_name().lower() == function_name.lower().strip():
                return tool.execute(function_args)
            
        return (f"invalid hallucination function_name {function_name}", 4)


class TreeNode:
    """
    The node of the tree
    """

    def __init__(self):
        # node state
        self.is_terminal = False
        self.is_root = False
        self.pruned = False
        self.finished = False

        self.reasoning = ""
        self.function_name = ""
        self.function_args = {}
        self.observation = ""
        self.observation_code = (
            None  # 0. action_answer, 1. final_answer; 2. give_up; 3. execution_failed; 4.hallucination;
        )

        self.father = None
        self.children = []

        self.expand_num = (
            0  # The number of visits to the node, 0 means it has not been visited
        )

        # openai-messages of this node
        self.messages = []

    def down_to_leaf_depth(self):
        """
        maximum depth of subtrees including self
        """
        max_depth = 0
        for child in self.children:
            max_depth = max(max_depth, child.down_to_leaf_depth())
        return max_depth + 1

    def depth(self):
        """
        maximum depth to root including self
        """
        if self.father is None:
            return 0
        return self.father.depth() + 1

    def get_size(self):
        """
        subtree, including itself
        """
        size = 1
        for child in self.children:
            size += child.get_size()
        return size

    def prune(self):
        """
        pruning off the subtree
        """
        self.pruned = True
        for child in self.children:
            child.prune()

    def print(self):
        """
        print the node data
        """
        if self.is_root:
            print("🌟Root🌟")
            return

        color_converter = {
            "Thought": "red",
            "Action": "blue",
            "Action Input": "cyan",
            "Final Answer": "green",
            "Reflection": "blue",
        }
        print(
            colored(
                f"Thought: {self.reasoning}",
                color=color_converter["Thought"],
            )
        )
        print(
            colored(
                f"Action: {self.function_name}, args: {self.function_args}",
                color=color_converter["Action"],
            )
        )

        if self.observation != "":
            if len(self.observation) < 1536:
                print(colored(f"Observation: {self.observation}", color="yellow"))
            else:
                print(
                    colored(
                        f"Observation: {self.observation[:1536]}......(len={len(self.observation)})",
                        color="yellow",
                    )
                )

    @classmethod
    def find_ancestor_intersection(cls, node1, node2):
        """
        find the first common ancestor
        """
        if node1 is None or node2 is None:
            return None
        if node1 == node2:
            return node1
        length1 = node1.depth()
        length2 = node2.depth()
        if length1 > length2:
            return TreeNode.find_ancestor_intersection(node1.father, node2)
        else:
            return TreeNode.find_ancestor_intersection(node1, node2.father)

    def get_train_messages_from_this_node(self):
        """
        Returns chained results, starting from this node up to the root node
        """

        raise NotImplementedError

    def get_chain_from_this_node(self, with_messages=False):
        """
        Returns chained results, starting from this node up to the root node
        """
        now_node = self
        result = []
        while now_node.father is not None:
            result = [now_node.to_json(with_messages=with_messages)] + result
            now_node = now_node.father
        return result

    def get_former_trice_from_this_node(
        self,
        end_node=None,
    ):
        """
        Return path description from end_node -> self
        Does not contain end_node, never contains root node
        """
        node = self
        output_str_list = []

        while node != end_node and node is not None and node.is_root is False:
            now_node_des_list = []
            now_node_des_list.append(f"Thought: {node.reasoning}\n")
            now_node_des_list.append(
                f"Action: {node.function_name}, args: {node.function_args}\n"
            )
            if node.observation != "":
                tuncated = node.observation
                if len(node.observation) > 1024:
                    tuncated = (
                        node.observation[:1024] + f"...(len={len(node.observation)})"
                    )
                now_node_des_list.append(f"Observation: {tuncated}\n")
            output_str_list = now_node_des_list + output_str_list
            node = node.father

        now_str = ""
        for k, cont in enumerate(output_str_list):
            now_str += f"step_{k+1}: {cont}\n"

        if now_str == "":
            now_str = "None"
        return now_str

    def to_json_recursive(self, with_messages=False):
        """
        Recursively put tree into json format
        """
        js_obj = self.to_json(with_messages=with_messages)
        js_obj["children"] = []
        for child in self.children:
            js_obj["children"].append(child.to_json_recursive())
        return js_obj

    def to_json(self, with_messages=False):
        """
        Convert the current node to json format
        """
        json_obj = {}
        json_obj["is_root"] = self.is_root
        if self.is_root is True:
            return json_obj

        json_obj["is_terminal"] = False
        json_obj["pruned"] = self.pruned
        json_obj["finished"] = self.finished

        json_obj["depth"] = self.depth()
        json_obj["function_name"] = self.function_name
        json_obj["function_args"] = self.function_args

        if self.observation != "":
            json_obj["observation"] = self.observation
        if self.observation_code is not None:
            json_obj["observation_code"] = self.observation_code
        json_obj["child_count"] = len(self.children)
        json_obj["expand_num"] = self.expand_num

        if with_messages:
            json_obj["messages"] = []
            for message in self.messages:
                if not ("valid" in message.keys() and message["valid"] is False):
                    json_obj["messages"].append(message["role"])
                else:
                    json_obj["messages"].append(message["role"] + "_invalid")

        return json_obj


class Tree:
    """
    The tree structure
    """

    def __init__(self):
        self.root = TreeNode()
        self.root.is_root = True

    def to_json_recursive(self, with_messages=False):
        """
        Recursively put tree into json format
        """
        tree_structure = self.root.to_json_recursive(with_messages=with_messages)
        js_obj = {
            "size": self.root.get_size(),
            "max_length": self.root.down_to_leaf_depth(),
            "tree": tree_structure,
        }
        return js_obj


class DFSReact:
    """
    The DFS decision maker
    """

    def __init__(self, llm, executor: Executor, input_description):
        self.llm = llm
        self.executor = executor
        self.tool_descriptions = executor.get_tools_descriptions()
        self.input_description = input_description
        self.forward_args = None
        self.tree = None
        self.restart()

    def restart(self):
        self.terminal_node = []
        self.give_up_node = []
        self.now_expand_num = 0
        self.query_count = 0
        self.total_tokens = 0

    def to_json(self, answer=False, process=True):
        """
        Convert the current node to json format
        """
        if self.tree is None:
            return {}

        if process:
            json_obj = {
                "tree": self.tree.to_json_recursive(),
                "forward_args": self.forward_args,
                "compare_candidates": [],
            }
            for node in self.terminal_node:
                if node.pruned is False:  # has answer
                    json_obj["compare_candidates"].append(
                        node.get_chain_from_this_node(with_messages=False)
                    )
        else:
            json_obj = {}

        if answer:
            json_obj["answer_generation"] = {
                "query_count": self.query_count,
                "total_tokens": self.total_tokens,
                "finish_type": None,
                "final_answer": "",
            }
            for node in self.terminal_node:
                if node.pruned is False:
                    json_obj["answer_generation"]["valid_data"] = True
                    json_obj["answer_generation"]["finish_type"] = "give_answer"
                    json_obj["answer_generation"]["final_answer"] = node.observation
                    break
            # do not have final answer, look for give_up
            if json_obj["answer_generation"]["finish_type"] is None:
                if len(self.give_up_node) > 0:
                    random_pos = random.randint(0, len(self.give_up_node) - 1)
                    choose_give_up_node = self.give_up_node[random_pos]
                    json_obj["answer_generation"]["finish_type"] = "give_up"
                    json_obj["answer_generation"][
                        "final_answer"
                    ] = choose_give_up_node.observation
        return json_obj

    def start(
        self,
        single_chain_max_step,
        tree_beam_size=2,
        max_query_count=50,
        answer_count_threshold=1,
        with_filter=True,
    ):
        """single_chain_max_step: The maximum depth of the tree
        tree_beam_size: How many children nodes for one node are generated per layer
        answer = n means to exit when find n "give_answer" nodes
        max_query_count: exiting when OpenAI-query exists this value
        with_filter: difference between normal DFS(with_filter=True) and DFSDT(with_filter=False).
        """
        self.forward_args = locals()
        if "self" in self.forward_args.keys():
            self.forward_args.pop("self")
        self.tree = Tree()

        system = FORMAT_INSTRUCTIONS_SYSTEM_FUNCTION
        system = system.replace("{tool_description}", self.tool_descriptions)
        self.tree.root.messages.append({"role": "system", "content": system})

        user = FORMAT_INSTRUCTIONS_USER_FUNCTION
        user = user.replace("{input_description}", self.input_description)
        self.tree.root.messages.append({"role": "user", "content": user})

        return self.DFS(
            self.tree.root,
            single_chain_max_step,
            tree_beam_size,
            max_query_count,
            answer_count_threshold,
            with_filter,
        )

    def DFS(
        self,
        now_node,
        single_chain_max_step,
        tree_beam_size,
        max_query_count,
        answer_count_threshold,
        with_filter=True,
    ):
        """
        Returns the number of search back steps.
        Branch search return: If the search is completed (whether the result is the final answer or give up), it means that the subtree where the parent node is located has no search value, and it will fall back to the grandparent node, Return 2. Otherwise return 1.
        Global search return: If the termination condition (the maximum number of queries or the number of terminal answers) is triggered, a number (100000) as large as possible will be returned to terminate the entire search result.
        """

        now_node.expand_num = self.now_expand_num
        self.now_expand_num += 1
        if (
            now_node.depth() >= single_chain_max_step
            or now_node.pruned
            or now_node.is_terminal
        ):
            if now_node.is_terminal:  # final answer
                self.terminal_node.append(now_node)
                return 2
            else:
                now_node.pruned = True
                if now_node.observation_code == 2:  # give
                    self.give_up_node.append(now_node)
                    return 2
                else:
                    return 1

        next_tree_split_nodes = []
        for i in range(tree_beam_size):
            temp_now_node = now_node

            # If a node have children now, We will prompt the model to generate different nodes than all the existing nodes
            delete_former_diversity_message = False
            diversity_message = None
            if len(temp_now_node.children) > 0:
                former_candidates_des = ""
                js_list = []
                for _, child in enumerate(temp_now_node.children):
                    obj_dict = {
                        "name": child.function_name,
                        "arguments": child.function_args,
                        "function_output": child.observation,
                    }
                    js_list.append(obj_dict)

                if len(js_list) > 0:
                    former_candidates_des = (
                        former_candidates_des + f"{json.dumps(js_list,indent=2)}\n"
                    )
                    if temp_now_node.observation != "":
                        former_candidates_des = (
                            former_candidates_des
                            + f"again, your former observation: {temp_now_node.observation}\n"
                        )
                    diverse_prompt = DIVERSITY_PROMPT
                    diverse_prompt = diverse_prompt.replace(
                        "{previous_candidate}", former_candidates_des
                    )
                    diversity_message = {"role": "user", "content": diverse_prompt}
                    temp_now_node.messages.append(diversity_message)

                    delete_former_diversity_message = True

            # on_llm_start

            self.llm.change_messages(temp_now_node.messages)
            new_message, total_tokens = self.llm.parse(functions=self.executor.get_tools_function())
            """
            print("************************************************************")
            for i, message in enumerate(temp_now_node.messages):
                print(f"message[{i}]: {message}")
            print(f"new generate message: {new_message}")
            print("************************************************************")
            """
            # on_llm_end
            self.query_count += 1
            self.total_tokens += total_tokens
            if self.query_count >= max_query_count:
                return 100000

            # We need to exclude the diversity_message, because it will influence child nodes
            if delete_former_diversity_message:
                temp_now_node.messages[-1]["valid"] = False

            # parse nodes from OpenAI-message like CoT method
            assert new_message["role"] == "assistant"
            temp_node = TreeNode()
            if "content" in new_message.keys() and new_message["content"] is not None:
                temp_node.reasoning = new_message["content"]

            if "function_call" in new_message.keys():
                function_name = new_message["function_call"]["name"]
                function_input = new_message["function_call"]["arguments"]
                temp_node.function_name = function_name
                temp_node.function_args = function_input
                args = json.loads(function_input)

                # temp_node.print()

                # on_tool_start
                observation, status = self.executor.step(function_name, args)
                temp_node.observation = observation
                temp_node.observation_code = status

                # check whether terminal
                # if '"return_type": "give_answer"' in action_input:
                temp_node.messages = deepcopy(temp_now_node.messages)
                temp_node.father = temp_now_node
                temp_now_node.children.append(temp_node)
                temp_node.print()
                temp_now_node = temp_node
                # on_tool_end
                if temp_node.observation_code == 3 or temp_node.observation_code == 2:
                    temp_now_node.pruned = True
                elif temp_node.observation_code == 4:  # hallucination api name
                    new_message["function_call"][
                        "name"
                    ] = "invalid_hallucination_function_name"
                    temp_now_node.pruned = True
                elif status == 1:  # final answer
                    temp_now_node.is_terminal = True
                temp_now_node.messages.append(new_message)
                temp_now_node.messages.append(
                    {
                        "role": "function",
                        "name": new_message["function_call"]["name"],
                        "content": temp_now_node.observation,
                    }
                )

            return_value = None
            if not with_filter:  # DFSDT
                result = self.DFS(
                    temp_now_node,
                    single_chain_max_step,
                    tree_beam_size,
                    max_query_count,
                    answer_count_threshold,
                    with_filter,
                )
                if len(self.terminal_node) >= answer_count_threshold:
                    return_value = 10000
                elif result > 1:
                    return_value = result - 1

            else:
                next_tree_split_nodes.append(temp_now_node)
            if return_value is not None:
                return return_value

        # Sort the generated next_tree_split_nodes nodes when normal DFS
        if len(next_tree_split_nodes) > 1:
            # When using normal DFS, if we have many child nodes, we will refer to LLM to compare and choose the best one to expand first
            # remember, this operator will cost extra OpenAI calls.
            llm_rank_args = {
                "tool_descriptions": self.tool_descriptions,
                "rank_func": rank2_subfix,
            }
            scores, rank_query_count, total_tokens = sum_based_rankn(
                self.llm, llm_rank_args=llm_rank_args, candidates=next_tree_split_nodes
            )
            self.query_count += rank_query_count
            self.total_tokens += total_tokens
            for score, node in zip(scores, next_tree_split_nodes):
                node.prior_score = score
            zip_value = list(
                zip(next_tree_split_nodes, range(len(next_tree_split_nodes)))
            )
            zip_value.sort(key=lambda x: x[0].prior_score, reverse=True)  # 先做score高的
            next_tree_split_nodes, _ = zip(*zip_value)

        # Choose one to expand
        for _, snode in enumerate(next_tree_split_nodes):  # type: ignore
            result = self.DFS(
                snode,
                single_chain_max_step,
                tree_beam_size,
                max_query_count,
                answer_count_threshold,
            )
            if len(self.terminal_node) >= answer_count_threshold:
                return 10000
            elif result > 1:
                return result - 1

        return 1

@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def chat_completion_request(
    key,
    messages,
    functions=None,
    function_call=None,
    model="gpt-3.5-turbo-16k-0613",
    stop=None,
    **args,
):
    use_messages = []
    for message in messages:
        if not ("valid" in message.keys() and message["valid"] == False):
            use_messages.append(message)

    json_data = {
        "model": model,
        "messages": use_messages,
        "max_tokens": 1024,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        **args,
    }
    if stop is not None:
        json_data.update({"stop": stop})
    if functions is not None:
        json_data.update({"functions": functions})
    if function_call is not None:
        json_data.update({"function_call": function_call})

    try:
        if model == "gpt-3.5-turbo-16k-0613":
            openai.api_key = key
        else:
            raise NotImplementedError
        openai_response = openai.ChatCompletion.create(
            **json_data,
        )
        json_data = json.loads(str(openai_response))
        return json_data

    except Exception as e:
        print("Unable to generate ChatCompletion response")
        print(f"OpenAI calling Exception: {e}")
        return e


class ChatGPTFunction:
    def __init__(self, model="gpt-3.5-turbo-16k-0613", openai_key=""):
        self.model = model
        self.conversation_history = []
        self.openai_key = openai_key
        self.time = time.time()
        self.TRY_TIME = 6

    def add_message(self, message):
        self.conversation_history.append(message)

    def change_messages(self, messages):
        self.conversation_history = messages

    def display_conversation(self):
        role_to_color = {
            "system": "red",
            "user": "green",
            "assistant": "blue",
            "function": "magenta",
        }
        print("before_print" + "*" * 50)
        for message in self.conversation_history:
            print_obj = f"{message['role']}: {message['content']} "
            if "function_call" in message.keys():
                print_obj = print_obj + f"function_call: {message['function_call']}"
            print_obj += ""
            print(
                colored(
                    print_obj,
                    role_to_color[message["role"]],
                )
            )
        print("end_print" + "*" * 50)

    def parse(self, functions, **args):
        self.time = time.time()
        conversation_history = self.conversation_history
        error_message = None
        for _ in range(self.TRY_TIME):
            if _ != 0:
                time.sleep(15)
            if functions != []:
                json_data = chat_completion_request(
                    self.openai_key, conversation_history, functions=functions, **args
                )
            else:
                json_data = chat_completion_request(
                    self.openai_key, conversation_history, **args
                )
            try:
                total_tokens = json_data["usage"]["total_tokens"]
                message = json_data["choices"][0]["message"]
                print(f"total tokens: {json_data['usage']['total_tokens']}")

                if (
                    "function_call" in message.keys()
                    and "." in message["function_call"]["name"]
                ):
                    message["function_call"]["name"] = message["function_call"][
                        "name"
                    ].split(".")[-1]

                return message, total_tokens
            except BaseException as e:
                error_message = f"LLM response parsing exception: {repr(e)}. Try again."
                if json_data is not None:
                    error_message = f"OpenAI return: {json_data}" + error_message
                print(error_message)

        return {"role": "assistant", "content": str(json_data)}, 0


if __name__ == "__main__":
    tools = [FinishTool(), TextCompletionTool()]
    executor = Executor(tools)
    llm = ChatGPTFunction(openai_key=os.getenv("OPENAI_API_KEY", ""))
    agent = DFSReact(llm, executor, "where is beijing")
    agent.start(3, with_filter=False)
    print(agent.to_json())
