import urllib
import pymongo
import os
import hashlib
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional
import pymongo.collection


def mongo_authenticate(path: str) -> pymongo.MongoClient:
    if os.environ.get('DOCKER_ENV'):
        host = os.environ.get('MONGO_HOST', 'db')
        
        try:
            with open(f'{path}.secrets/mongodb_user.txt', 'r') as f_open:
                username = f_open.readlines()[0].strip()
        except FileNotFoundError:
            raise ValueError("mongodb_user.txt not found in .secrets directory")
        
        try:
            with open(f'{path}.secrets/mongodb_pwd.txt', 'r') as f_open:
                password = f_open.readlines()[0].strip()
        except FileNotFoundError:
            raise ValueError("mongodb_pwd.txt not found in .secrets directory")
    else:
        try:
            with open(f'{path}.secrets/host.txt', 'r') as f_open:
                host = f_open.readlines()[0].strip()
        except FileNotFoundError:
            host = 'localhost'
        
        try:
            with open(f'{path}.secrets/mongodb_user.txt', 'r') as f_open:
                username = f_open.readlines()[0].strip()
        except FileNotFoundError:
            raise ValueError("mongodb_user.txt not found in .secrets directory")
        
        try:
            with open(f'{path}.secrets/mongodb_pwd.txt', 'r') as f_open:
                password = f_open.readlines()[0].strip()
        except FileNotFoundError:
            raise ValueError("mongodb_pwd.txt not found in .secrets directory")

    host = urllib.parse.quote_plus(host)
    username = urllib.parse.quote_plus(username)
    password = urllib.parse.quote_plus(password)
    port = 27017

    client = pymongo.MongoClient(
        f'mongodb://{username}:{password}@{host}:{port}', authSource='admin'
    )
    return client


def extract_last_url_element(url: str) -> str:
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    filename = path_parts[-1]
    return filename


def insert_many_tweets(col: pymongo.collection, docs: List[Dict[str, Any]]):
    col.insert_many(docs)


def insert_one_tweet(col: pymongo.collection, doc: Dict[str, Any]):
    col.insert_one(doc)


def get_tweet_by_id(col: pymongo.collection, id: str) -> Optional[Dict[str, Any]]:
    return col.find_one({"id_str": id})


def get_tweets_by_username(col: pymongo.collection, username: str) -> Optional[Dict[str, Any]]:
    return [i for i in col.find({"username_str": username})]


def get_tweet_by_username(col: pymongo.collection, username: str) -> Optional[Dict[str, Any]]:
    return col.find_one({"username_str": username})


def get_all_tweets(col: pymongo.collection) -> List[Dict[str, Any]]:
    return col.find({})


def get_hash_of_all_tweets(col_tweets: pymongo.collection, username: str = None) -> List[str]:
    if username:
        return [i["hash256_str"] for i in col_tweets.find({"username_str": username}, {"hash256_str": 1, "_id": 0})]
    return [i["hash256_str"] for i in col_tweets.find({}, {"hash256_str": 1, "_id": 0})]


def __extract_media(media_url: str, binary_data: bytes) -> None:
    filename = os.path.join("./", extract_last_url_element(media_url))
    with open(filename, "wb") as file:
        file.write(binary_data)
    print(f"Saved image file to {filename}")


def get_attachments(attachment_col: pymongo.collection, id: str) -> None:
    attachments = attachment_col.find_one({"ref_tweet_id_str": id})
    if attachments is not None:
        for a in attachments["attachments_list"]:
            __extract_media(a["media_url_str"], a["binary_data_bytes"])
    else:
        print("Tweet not found.")


def hash_object(obj: str) -> str:
    if (isinstance(obj, bytes)):
        obj_bytes = obj
    else:
        obj_bytes = str.encode(obj)

    hash_object = hashlib.sha256(obj_bytes)
    hex_dig = hash_object.hexdigest()
    return hex_dig


if __name__ == '__main__':
    try:
        db = mongo_authenticate('./')['xdb']
        cols = db.list_collection_names()
        print('Connection working:', cols)
    except Exception as e:
        print('Connection not working.')
        print(e)
        exit(1)