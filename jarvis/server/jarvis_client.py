import grpc
import json
import time
import jarvis.server.jarvis_pb2 as jarvis_pb2
import jarvis.server.jarvis_pb2_grpc as jarvis_pb2_grpc
from google.protobuf.json_format import MessageToJson


tweet_extraction = """Provide tweets about TiDB on Twitter in the past day, and insert these tweets data into TiDB cloud tables.
* "TiDB Cloud", "TiDB", "PingCAP", "tidbcloud" are some useful tweet search query keywords, and exclude the retweet e.g. query='(tidb OR pingcap OR TiDB Cloud OR tidbcloud) -is:retweet'.
* These tweets' topic should be "TiDB" in the tidb cloud tables.
* The bearer token should be fetched from the environment variable TWEET_BEARER_TOKEN.
* The start_time query parameter value should be an RFC3339 date-time for the past day, formatted correctly as 'YYYY-MM-DDTHH:MM:SSZ'.
* The max_results query parameter value should be 100.
* In addition to the above requirements, please make sure to fetch the following tweet fields when making the request: 'public_metrics', "id", "created_at", "referenced_tweets".  Ensure the correct format and presence of all required fields in the response.
* Please avoid the error (1062, "Duplicate entry '?' for key 'tweets.PRIMARY'") while inserting the tweets data into tidb cloud tables.
* Please checkout the http response status, raise an error if the status is not 200.
* Finally here a simple specification that you need
# Response schema for https://api.twitter.com/2/tweets/search/recent
{
   "type": "object",
   "properties": {
     "data": {
       "type": "array",
       "items": {
         "type": "object",
         "properties": {
           "public_metrics": {
             "type": "object",
             "properties": {
               "retweet_count": {"type": "integer"},
               "reply_count": {"type": "integer"},
               "like_count": {"type": "integer"},
               "quote_count": {"type": "integer"},
               "bookmark_count": {"type": "integer"},
               "impression_count": {"type": "integer"}
             },
             "required": ["retweet_count", "reply_count", "like_count", "quote_count", "bookmark_count", "impression_count"]
           },
           "id": {
             "type": "string"
           },
           "referenced_tweets": {
             "type": "array",
             "items": {
               "type": "object",
               "properties": {
                 "type": {"type": "string"},
                 "id": {"type": "string"}
               },
               "required": ["type", "id"]
             }
           },
           "created_at": {
             "type": "string",
             "format": "date-time"
           },
           "text": {
             "type": "string"
           }
         },
         "required": ["public_metrics", "id", "created_at", "text"]
       }
     }
   },
   "required": ["data"]
 }
 
# Table schema in TiDB Cloud Database (mysql protocol)

use jarvis_store;

CREATE TABLE tweets (
    id BIGINT PRIMARY KEY,
    created_at DATETIME,
    topic VARCHAR(64),
    text TEXT
);

CREATE TABLE tweets_public_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tweet_id BIGINT UNIQUE KEY,
    retweet_count INT,
    reply_count INT,
    like_count INT,
    quote_count INT,
    bookmark_count INT,
    impression_count INT,
    FOREIGN KEY (tweet_id) REFERENCES tweets(id)
);

CREATE TABLE referenced_tweets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tweet_id BIGINT UNIQUE KEY,
    referenced_type VARCHAR(255),
    referenced_tweet_id BIGINT,
    FOREIGN KEY (tweet_id) REFERENCES tweets(id)
);

# How to connect to TiDB Cloud Database (mysql protocol)

import pymysql
import os

def connect_to_db():
    \"\"\"
    example:
    # Create a connection to the TiDB Cloud database
    connection = connect_to_mysql_db()

    # Check if the connection was successful
    try:
        with connection.cursor() as cursor:
            ...
    finally:
        connection.close()
    \"\"\"

    user = os.getenv("TIDB_USER")
    password = os.getenv("TIDB_PASSWORD")
    host = os.getenv("TIDB_HOST")
    port = os.getenv("TIDB_PORT") or 4000
    database = os.getenv("TIDB_DATABASE", "jarvis_store")
    assert user is not None
    assert password is not None
    assert host is not None

    connection = pymysql.connect(
        host=host,
        user=user,
        port=int(port),
        password=password,
        database=database,
        ssl={'ca': '/etc/ssl/cert.pem'}
    )  

    return connection
"""

tweet_analysis = """write a twitter analysis report related to TiDB and CockroachDB to understand their presence and influence in social media. the Guides:
1. Load tweets, tweets_public_metrics, referenced_tweets into pandas dataframe for further analysis
2. Generate code to do the following analysis at least:
  * Tweet Volume Analysis: Compare the number of tweets for each product (TiDB and CockroachDB) over a defined period of time.
  * Impression Analysis: Calculate the total impressions for tweets related to each product and identify tweets that had the highest impression count.
  * Interaction Type Analysis: Analyze how many of the tweets for each product are original vs. replies or retweets.
3. Generate a analysis report file named `tidb_and_cockroach_tweets_analysis_report.md` using markdown format

In adddition, the following are some QA that you need

# how to store pandas dataframe into jvm, and load dataframe from jvm

save dataframe: jvm.set("tweets_df.seq1.df", tweets_df.to_json())
get dataframe: tweets_df = pd.read_json(jvm.get("tweets_df.seq1.df"))

# Table schema in TiDB Cloud Database (mysql protocol)

use jarvis_store;

CREATE TABLE tweets (
    id BIGINT PRIMARY KEY,
    created_at DATETIME,
    topic VARCHAR(64),
    text TEXT
);

CREATE TABLE tweets_public_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tweet_id BIGINT UNIQUE KEY,
    retweet_count INT,
    reply_count INT,
    like_count INT,
    quote_count INT,
    bookmark_count INT,
    impression_count INT,
    FOREIGN KEY (tweet_id) REFERENCES tweets(id)
);

CREATE TABLE referenced_tweets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tweet_id BIGINT UNIQUE KEY,
    referenced_type VARCHAR(255),
    referenced_tweet_id BIGINT,
    FOREIGN KEY (tweet_id) REFERENCES tweets(id)
);

# How to distinguish TiDB and CockroachDB tweets

TiDB tweets: tweets.topic='TiDB'
CockroachDB tweets: tweets.topic='CockroachDB'

# How to connect to TiDB Cloud Database (mysql protocol)

import pymysql
import os

def connect_to_db():
    \"\"\"
    example:
    # Create a connection to the TiDB Cloud database
    connection = connect_to_mysql_db()

    # Check if the connection was successful
    try:
        with connection.cursor() as cursor:
            ...
    finally:
        connection.close()
    \"\"\"

    user = os.getenv("TIDB_USER")
    password = os.getenv("TIDB_PASSWORD")
    host = os.getenv("TIDB_HOST")
    port = os.getenv("TIDB_PORT") or 4000
    database = os.getenv("TIDB_DATABASE", "jarvis_store")
    assert user is not None
    assert password is not None
    assert host is not None

    connection = pymysql.connect(
        host=host,
        user=user,
        port=int(port),
        password=password,
        database=database,
        ssl={'ca': '/etc/ssl/cert.pem'}
    )

    return connection
"""


def train_skill(stub, task):
    response = stub.Execute(
        jarvis_pb2.ExecuteRequest(
            task=task,
        )
    )
    print(f"Jarvis client received: {response}")


def save_skill(stub, agent_id, skill_name):
    response = stub.SaveSkill(
        jarvis_pb2.SaveSkillRequest(
            agent_id=agent_id,
            skill_name=skill_name,
        )
    )
    print(f"Jarvis client received: {MessageToJson(response)}")


def replay(stub, agent_id):
    response = stub.ChainExecute(
        jarvis_pb2.GoalExecuteRequest(
            goal=f"replay {agent_id}",
            agent_id=agent_id,
            skip_gen=True,
            enable_skill_library=False,
        )
    )
    print(f"Jarvis client received: {MessageToJson(response)}")


if __name__ == "__main__":
    channel = grpc.insecure_channel("localhost:51155")
    stub = jarvis_pb2_grpc.JarvisStub(channel)
    # replay(stub, "c54d26ae919acdd180263e8efe995947")
    save_skill(
        stub,
        "c54d26ae919acdd180263e8efe995947",
        "generate_tidb_and_cockroach_tweets_analysis_report",
    )
    # train_skill(stub, tweet_analysis)
