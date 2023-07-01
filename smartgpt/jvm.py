import ast
import logging
import json
import os

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
    except Exception as e:
        logging.fatal(f"get, An error occurred: {e}")
        return default

def set(key, value):
    global kv_store
    try:
        if isinstance(value, list):
            value = repr(value)
        kv_store[key] = value
        save_kv_store()
    except Exception as error:
        logging.fatal(f"set, An error occurred: {error}")


def list_values_with_key_prefix(prefix):
    try:
        values = []
        for key in kv_store.keys():
            if key.startswith(prefix):
                values.append(get(key))
        #logging.info(f"list_values_with_key_prefix, values: {values}")
        return values
    except Exception as e:
        logging.fatal(f"list_values_with_key_prefix, An error occurred: {e}")
        return []

def list_keys_with_prefix(prefix):
    try:
        keys = [key for key in kv_store.keys() if key.startswith(prefix)]
        return keys
    except Exception as e:
        logging.fatal(f"list_keys_with_prefix, An error occurred: {e}")
        return []

def set_loop_idx(value):
    set("idx", value)