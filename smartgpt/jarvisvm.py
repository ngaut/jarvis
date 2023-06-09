import pymysql
import ast
import logging
import gpt
import re

from abc import ABC
from urllib.error import HTTPError
from bs4 import BeautifulSoup
import googlesearch
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager


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

def get_json(key):
    try:
        cur.execute("SELECT value FROM kv_store WHERE jarvis_key=%s", (key,))
        value = cur.fetchone()
        if value is not None:
            value = value[0]
        logging.info(f"get, key: {key}, value: {value}")
        return value
    except Exception as e:
        logging.fatal(f"get, An error occurred: {e}")



def set_json(jarvis_key, value):
    try:
        logging.debug(f"set, jarvis_key: {jarvis_key}, value: {value}")
        value = json.dumps(value, ensure_ascii=False)

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
            kv_dict[key] = value
        return kv_dict
    except Exception as e:
        logging.fatal(f"all, An error occurred: {e}")


# remember to close the connection when you're done
def close_db():
    conn.close()


def list_json_with_key_prefix(prefix):
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


def extract_info(url:str, prompt:str) -> str:
    html = get_html(url)
    text = extract_text(html)
    user_message_content = f"{prompt}\n\n```{text}```"

    extracted_info = gpt.complete(user_message_content, model=gpt.GPT_3_5_TURBO)
    return extracted_info

def get_html(url: str) -> str:
    options = ChromeOptions()
    options.headless = True
    browser = ChromeWebDriver(executable_path=ChromeDriverManager().install(), options=options)
    browser.get(url)
    html = browser.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
    browser.quit()
    return html

def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = "\n".join(chunk for chunk in chunks if chunk)
    return text
