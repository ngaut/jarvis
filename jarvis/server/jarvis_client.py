import grpc
import json
import time
import jarvis.server.jarvis_pb2 as jarvis_pb2
import jarvis.server.jarvis_pb2_grpc as jarvis_pb2_grpc
from google.protobuf.json_format import MessageToJson


long_task1 = """Provide tweets about TiDB on Twitter in the past day, and insert these tweets data into tidb cloud tables.
* "TiDB Cloud", "TiDB", "PingCAP", "tidbcloud" are some useful tweet search query keywords, and exclude the retweet e.g. query='(tidb OR pingcap OR TiDB Cloud OR tidbcloud) -is:retweet'.
* The bearer token should be fetched from the environment variable TWEET_BEARER_TOKEN.
* The start_time query parameter value should be an RFC3339 date-time for the past day, formatted correctly as 'YYYY-MM-DDTHH:MM:SSZ'.
* In addition to the above requirements, please make sure to fetch the following tweet fields when making the request: 'public_metrics', "id", "created_at", "referenced_tweets".  Ensure the correct format and presence of all required fields in the response.
* Please avoid the error (1062, "Duplicate entry '?' for key 'tweets.PRIMARY'") while inserting the tweets data into tidb cloud tables.
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
         "required": ["public_metrics", "edit_history_tweet_ids", "id", "referenced_tweets", "created_at", "text"]
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

long_task2 = """Create a comprehensive MySQL test case that encapsulates the concept of stored procedures, following this article from https://www.freecodecamp.org/news/how-to-simplify-database-operations-using-mysql-stored-procedures/.

The case should consist of:
* Necessary table creation to set up the initial database environment: database creation, table creation, and sample data insertion
* Definition and creation of a stored procedure, showcasing best practices as defined in the aforementioned article.
* Execution of the stored procedure to validate its functionality.

Ensure that the case is self-contained, meaning it can be run on any MySQL environment and demonstrate the end-to-end process of utilizing stored procedures in MySQL.
"""

long_task3 = """Considering that TiDB does not support functions and keywords such as stored procedure, UNTIL, WHILE, and their related statements (create procedure, call procedure, drop procedure, UNTIL... end, REPEAT, and WHILE ... DO ... END WHILE). 
Given the provided MySQL stored procedure case, translate it into TiDB SQL syntax and run it on TiDB Cloud Database. 
Some instructions:
* Stored procedures can be converted to views if they're query-based, lack procedural elements, and produce a single, deterministic result set without side effects."""

def run():
    channel = grpc.insecure_channel("localhost:51155")
    stub = jarvis_pb2_grpc.JarvisStub(channel)

    """
    response = stub.Execute(
        jarvis_pb2.ExecuteRequest(
            task=long_task3,
            agent_id="xxxx",
        )
    )
    print(f"Jarvis client received: {response}")
    """

    """
    response = stub.SaveSkill(
        jarvis_pb2.SaveSkillRequest(
            agent_id="xxxx",
            skill_name="convert_store_procedure_case",
        )
    )
    print(f"Jarvis client received: {MessageToJson(response)}")
    """

    response = stub.ChainExecute(
        jarvis_pb2.GoalExecuteRequest(
            goal= "{\"Task description\": \"Provide tweets about TiDB on Twitter in the past day.  \\\"TiDB Cloud\\\", \\\"TiDB\\\", \\\"PingCAP\\\", \\\"tidbcloud\\\" are some useful tweet search query keywords, e.g. query='(tidb OR pingcap OR tidb serverless)'. The bearer token should be fetched from the environment variable TWEET_BEARER_TOKEN. The start_time query parameter value should be an RFC3339 date-time for the past day, formatted correctly as 'YYYY-MM-DDTHH:MM:SSZ'.  In addition to the above requirements, please make sure to fetch the following tweet fields when making the request: 'public_metrics', \\\"entities\\\", \\\"id\\\", \\\"created_at\\\", \\\"referenced_tweets\\\". If any previous results included tweets that were retweeted, make sure to exclude those in the new results. Ensure the correct format and presence of all required fields in the response.\", \"Guide\": \"To handle the errors identified previously, ensure that the date for the past day is generated correctly in RFC3339 format. Also, check the code for parsing a block mapping and make sure the socket connection is stable. The bearer token should be fetched correctly from the environment variable TWEET_BEARER_TOKEN. Lastly, ensure that the search query includes the specified keywords and excludes retweets.\"}",
            agent_id="xxxx",
            enable_skill_library=True,
        )
    )
    print(f"Jarvis client received: {MessageToJson(response)}")
    exit()
    time.sleep(10)

    response = stub.ChainExecute(
        jarvis_pb2.GoalExecuteRequest(
            goal=long_task3,
            agent_id="xxxx",
            enable_skill_library=True,
        )
    )
    print(f"Jarvis client received: {MessageToJson(response)}")

if __name__ == "__main__":
    run()