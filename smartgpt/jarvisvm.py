

import os

def get(key):
    # read the whole file
    with open(key, 'r') as f:
        value = f.read()
    return value

def set(key, value):
    with open(key, 'w') as f:
        f.write(value)

def all():
    # construct a dictionary
    dict = {}
    for filename in os.listdir():
        with open(filename, 'r') as f:
            value = f.read()
        dict[filename] = value
    return dict
