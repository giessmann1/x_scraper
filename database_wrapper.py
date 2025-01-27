import urllib
import pymongo
import os
import hashlib
from urllib.parse import urlparse

# Returns connection object at database level
def mongo_authenticate(path):
    with open(f'{path}.secrets/host.txt', 'r') as f_open:
        host = f_open.readlines()[0]
    host = urllib.parse.quote_plus(host)

    port = 27017
    with open(f'{path}.secrets/mongodb_user.txt', 'r') as f_open:
        username = f_open.readlines()[0]
    username = urllib.parse.quote_plus(username)
    with open(f'{path}.secrets/mongodb_pwd.txt', 'r') as f_open:
        password = f_open.readlines()[0]
    password = urllib.parse.quote_plus(password)

    client = pymongo.MongoClient(
        f'mongodb://{username}:{password}@{host}:{port}', authSource='admin'
    )
    return client

def extract_last_url_element(url):
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    filename = path_parts[-1]
    return filename

def insert_new_tweets(col, docs):
    col.insert_many(docs)

def insert_one_tweet(col, doc):
    col.insert_one(doc)

def get_tweet_by_id(col, id):
    return col.find_one({"id": id})

def get_all_tweets(col):
    return col.find({})

def get_hash_of_all_tweets(col_tweets):
    return [i["hash256"] for i in col_tweets.find({}, {"hash256": 1, "_id": 0})]

def get_hash_of_all_tweet_comments(col_comments, id):
    return [i["hash256"] for i in col_comments.find({"id": id}, {"hash256": 1, "_id": 0})]

def extract_media(media_url, binary_data):
    filename = os.path.join("./", extract_last_url_element(media_url))
    # Write the binary data to file
    with open(filename, "wb") as file:
        file.write(binary_data)

    print(f"Saved image file to {filename}")

# SHA-256 a given object
def hash_object(obj):
    if (isinstance(obj, bytes)):
        obj_bytes = obj
    else:
        obj_bytes = str.encode(obj)

    hash_object = hashlib.sha256(obj_bytes)
    hex_dig = hash_object.hexdigest()
    return hex_dig
    
# Run the module directly to check if connection work
if __name__ == '__main__':
    try:
        db = mongo_authenticate('./')['xdb']
        cols = db.list_collection_names()
        print('Connection working:', cols)
    except Exception as e:
        print('Connection not working.')
        print(e)
        exit(1)