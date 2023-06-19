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

def get(key):
    global kv_store
    try:
        value = kv_store.get(key, None)
        if value is not None:
            try:
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass  # value is not a string representation of a list, so leave it as is
        return value
    except Exception as e:
        logging.fatal(f"get, An error occurred: {e}")
        return None

def set(key, value):
    global kv_store
    try:
        if isinstance(value, list):
            value = repr(value)
        kv_store[key] = value
        save_kv_store()
    except Exception as error:
        logging.fatal(f"set, An error occurred: {error}")

def all():
    global kv_store

    try:
        kv_dict = {}
        for key, value in kv_store.items():
            try:
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass  # value is not a string representation of a list, so leave it as is
            kv_dict[key] = value
        return kv_dict
    except Exception as e:
        logging.fatal(f"all, An error occurred: {e}")
        return {}

def list_values_with_key_prefix(prefix):
    try:
        values = []
        for key in kv_store.keys():
            if key.startswith(prefix):
                values.extend(get(key))
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
