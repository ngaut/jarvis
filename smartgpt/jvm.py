import os
import ast
import logging
import json

from smartgpt import utils

# initialize a dictionary when the module is imported
kv_store_file = "kv_store.json"
kv_store = {}

def load_kv_store():
    global kv_store
    global kv_store_file
    # Load the kv_store dictionary from the file if it exists
    if os.path.exists(kv_store_file):
        with open(kv_store_file, 'r') as f:
            kv_store = json.load(f)
    else:
        kv_store = {}

def save_kv_store():
    global kv_store
    global kv_store_file
    with open(kv_store_file, 'w') as f:
        json.dump(kv_store, f)

def get(key, default=None):
    global kv_store
    try:
        value = kv_store.get(key, None)
        if value is None:
            return default
        if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
            # This is a list
            return list(ast.literal_eval(value))
        return value
    except Exception as err:
        logging.fatal(f"get, An error occurred: {err}")
        return default

def set(key, value):
    global kv_store
    try:
        if isinstance(value, list):
            value = repr(value)
        kv_store[key] = value
        save_kv_store()
    except Exception as err:
        logging.fatal(f"set, An error occurred: {err}")


def list_values_with_key_prefix(prefix):
    try:
        values = []
        for key in kv_store.keys():
            if key.startswith(prefix):
                values.append(get(key))
        #logging.info(f"list_values_with_key_prefix, values: {values}")
        return values
    except Exception as err:
        logging.fatal(f"list_values_with_key_prefix, An error occurred: {err}")
        return []

def list_keys_with_prefix(prefix):
    try:
        keys = [key for key in kv_store.keys() if key.startswith(prefix)]
        return keys
    except Exception as err:
        logging.fatal(f"list_keys_with_prefix, An error occurred: {err}")
        return []

def set_loop_idx(value):
    set("idx", value)

LAZY_EVAL_PREFIX = "jvm.eval("

def eval(text, lazy_eval_prefix=LAZY_EVAL_PREFIX):
    # find last occurrence of "jvm.eval("
    start = text.rfind(lazy_eval_prefix)
    if start == -1:
        return None

    prefix_len = len(lazy_eval_prefix)
    # find the corresponding closing tag with parentheses balance
    rest = text[start+prefix_len:]
    balance = 0
    end = 0
    for char in rest:
        if char == '(':
            balance += 1
        elif char == ')':
            if balance == 0:
                break
            balance -= 1
        end += 1

    if balance != 0:
        logging.critical(f"Error: parentheses are not balanced in {text}")
        return None

    logging.info(f"eval_and_patch_template_before_exec, {start}-{end} text: {text}\n")

    # adjust the end position relative to the original string
    end = end + start + prefix_len
    # evaluate the substring between jvm.eval( and )
    expression = text[start+prefix_len:end].strip()

    try:
        evaluated = utils.sys_eval(expression)
    except Exception as err:
        logging.critical(f"Failed to evaluate {expression}. Error: {str(err)}")
        return None

    # replace the evaluated part in the original string
    text = text[:start] + str(evaluated) + text[end+1:]
    logging.info(f"text after patched: {text}\n")

    return text
