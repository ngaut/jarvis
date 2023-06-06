import pymysql
import ast
import logging
import gpt
import re

# establish a connection when the module is imported
conn = pymysql.connect(
    host="gateway01.us-west-2.prod.aws.tidbcloud.com",
    port=4000,
    user="2h94vMZq1EH7dut.root",
    password="2E3eKT87kCC4C6Op",
    database="jarvis",
    ssl={"ca": "/etc/ssl/cert.pem"}
)
cur = conn.cursor()

# create table if it doesn't exist
cur.execute('''CREATE TABLE IF NOT EXISTS `kv_store` (`jarvis_key` text(512), `value` text(65535), PRIMARY KEY (`jarvis_key`(512)))''')

def get(key):
    try:
        cur.execute("SELECT value FROM kv_store WHERE jarvis_key=%s", (key,))
        value = cur.fetchone()
        logging.debug(f"get, key: {key}, value: {value}")
        if value is None or value[0] is None:
            return None
        else:
            # Convert the value back to a list if it's a string representation of a list
            try:
                value = eval(value[0])
            except (ValueError, SyntaxError, TypeError):
                pass  # value is not a string representation of a list, so leave it as is
            return value
    except Exception as e:
        logging.fatal(f"get, An error occurred: {e}")


def get_values(key):
    try:
        cur.execute("SELECT value FROM kv_store WHERE jarvis_key=%s", (key,))
        value = cur.fetchone()
        logging.debug(f"get, key: {key}, value: {value}")
        if value is None or value[0] is None:
            return None
        else:
            # Convert the value back to a list if it's a string representation of a list
            try:
                value = eval(value[0])
            except (ValueError, SyntaxError, TypeError):
                pass  # value is not a string representation of a list, so leave it as is
            return value
    except Exception as e:
        logging.fatal(f"get, An error occurred: {e}")



def set(jarvis_key, value):
    try:
        if isinstance(value, list):
            value = repr(value)
        logging.debug(f"set, jarvis_key: {jarvis_key}, value: {value}")

        # Insert the value into the database
        cur.execute("INSERT INTO `kv_store` (`jarvis_key`, `value`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `value` = %s", (jarvis_key, value, value))
        conn.commit()
    except Exception as error:
        logging.fatal(f"set, An error occurred: {error}")



def all():
    try:
        cur.execute("SELECT * FROM kv_store")
        kv_dict = {}
        for key, value in cur.fetchall():
            try:
                # Convert the value back to a list if it's a string representation of a list
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass  # value is not a string representation of a list, so leave it as is
            kv_dict[key] = value
        return kv_dict
    except Exception as e:
        logging.fatal(f"all, An error occurred: {e}")


# remember to close the connection when you're done
def close_db():
    conn.close()


def list_values_with_key_prefix(prefix):
    try:
        cur.execute("SELECT `value` FROM `kv_store` WHERE `jarvis_key` LIKE %s", (prefix + "%",))
        values = []
        for value, in cur.fetchall():
            try:
                # Convert the value back to a list if it's a string representation of a list
                value = eval(value)
            except (ValueError, SyntaxError):
                pass  # value is not a string representation of a list, so leave it as is
            values.append(value)
        return values
    except Exception as e:
        logging.fatal(f"list_values_with_key_prefix, An error occurred: {e}")


# list_keys_with_prefix
def list_keys_with_prefix(prefix):
    try:
        cur.execute("SELECT key FROM kv_store WHERE jarvis_key LIKE %s", (prefix + "%",))
        keys = [key for key, in cur.fetchall()]
        return keys
    except Exception as e:
        logging.fatal(f"list_keys_with_prefix, An error occurred: {e}")


def text_completion(prompt:str):
    resp = gpt.complete(prompt=prompt, model = gpt.GPT_3_5_TURBO)
    return resp
    
