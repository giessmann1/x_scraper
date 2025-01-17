import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime, timedelta
import requests
import database_wrapper
import random
import bson
import re
import argparse

STATS_LEGEND = ["replies", "reposts", "quotes", "likes", "views_video"]
ID_NAME = "id"
DATETIME_NAME = "datetime_utc"
LINKS_NAME = "links"
MEDIA_NAME = "attachments"
TEXT_NAME = "text"
REPOST_NAME = "repost"
WAITING_TIME_DAYS = 7 # Time period to wait until tweet is scraped (providing enough time for people to reply)
USER_NAME_USERNAME = "profile_username"
USER_NAME_FULLNAME = "profile_fullname"
IS_REPOST = "is_repost"
COMMENTER_NAME_USERNAME = "commenter_username"
COMMENTER_NAME_FULLNAME = "commenter_fullname"
COMMENT_LIMIT = 10
SLEEPER_MIN = 8
BSON_SIZE_LIMIT = 16793600
HASHTAG_NAME = "hashtags"
MENTIONS_NAME = "mentions"
ATTACHMENTS_DB = "attachments"
COMMENTS_DB = "comments"
TWEETS_DB = "tweets"
ATTACHMENTS = True

def us_number_to_int(string):
    string_transformed = string.strip().replace(",", "")
    if string_transformed == "GIF" or string_transformed == "":
        return 0
    return int(string_transformed)

def parse_timeline_tweet(tweet, existing_entries):
    soup = BeautifulSoup(tweet.get_attribute("outerHTML"), "html.parser")
    # Stats
    stats_raw = soup.find_all("span", class_="tweet-stat")
    if len(stats_raw) == 0: return None # Filter load newest entry
    contents = {}
    for ids, s in enumerate(stats_raw):
        contents.update({STATS_LEGEND[ids]: us_number_to_int(s.getText())})

    text = soup.find("div", class_ = "tweet-content")
    links = [l.getText() for l in text.find_all("a")]
    hashtags = []
    mentions = []
    if len(links) > 0:
        for l in links:
            if re.search("#[A-Za-z0-9_]+", l):
                hashtags.append(l)
            if re.search("@[A-Za-z0-9_]+", l):
                mentions.append(l)
        if len(hashtags) > 0:
            contents.update({HASHTAG_NAME: hashtags})
        if len(mentions) > 0:
            contents.update({MENTIONS_NAME: mentions})
        links = [l for l in links if l not in hashtags + mentions]
        if len(links) > 0:
            contents.update({LINKS_NAME: links})
    text = text.get_text()

    # Datetime and url
    datetime_raw = soup.find("span", class_ = "tweet-date").find("a")
    id = database_wrapper.extract_last_url_element(datetime_raw["href"])
    datetime_unparsed = datetime_raw["title"]
    datetime_utc = datetime.strptime(datetime_unparsed, "%b %d, %Y · %I:%M %p %Z")
    datetime_utc_str = datetime_utc.isoformat()

    # Check if already exist
    hash_value = database_wrapper.hash_object(text + datetime_utc_str)
    if hash_value in existing_entries:
        print("Tweet already scraped.")
        return -1
    
    # Check if old enough
    days_old = datetime.now() - datetime_utc
    if days_old < timedelta(days = WAITING_TIME_DAYS):
        print("Tweet not old enough to be scraped, skip.")
        return None # Tweet to old enough to be scraped
    contents.update({ID_NAME: id, DATETIME_NAME: datetime_utc_str})

    # Check if post is a reply
    repost_header = soup.find("div", class_ = "retweet-header")
    if repost_header is not None:
        contents.update({IS_REPOST: True})
    else:
        contents.update({IS_REPOST: False})

    user_raw = soup.find("div", class_ = "tweet-header").find("a", class_ = "fullname")
    contents.update({USER_NAME_USERNAME: user_raw["href"].replace("/", ""), USER_NAME_FULLNAME: user_raw.get_text()})

    media_raw = soup.find("div", class_ = "attachments")
    media = []
    if media_raw is not None:
        img = media_raw.find_all("img")
        if len(img) > 0:
            images = [{"media_url": i["src"], "binary_data": requests.get(i["src"]).content} for i in img]
            media.extend(images)
        video = media_raw.find_all("video")
        if len(video) > 0:
            videos = [{"media_url": v.find("source")["src"], "binary_data": requests.get(v.find("source")["src"]).content} for v in video]
            media.extend(videos)
        if len(media) > 0:
            for m in media:
                if len(bson.BSON.encode(m)) >= BSON_SIZE_LIMIT:
                    m["binary_data"] = "To large to store in database."
            contents.update({MEDIA_NAME: [m["media_url"] for m in media]})
            if ATTACHMENTS: database_wrapper.insert_one_tweet(attachments_con, {ID_NAME: id, MEDIA_NAME: media})
            hash_value = database_wrapper.hash_object(text + datetime_utc_str + str(media))
            if hash_value in existing_entries:
                print("Tweet already scraped.")
                return -1

    # Check if hash_value exists in database
    contents.update({TEXT_NAME: text, "hash256": hash_value})
    return contents

def parse_conversation_tweet(reply):
        soup = BeautifulSoup(reply.get_attribute("outerHTML"), "html.parser")
        # Stats
        stats_raw = soup.find_all("span", class_="tweet-stat")
        if len(stats_raw) == 0: return None # Filter load newest entry
        contents = {}
        for ids, s in enumerate(stats_raw):
            contents.update({STATS_LEGEND[ids]: us_number_to_int(s.getText())})

        text = soup.find("div", class_ = "tweet-content")
        links = [l.getText() for l in text.find_all("a")]
        hashtags = []
        mentions = []
        if len(links) > 0:
            for l in links:
                if re.search("#[A-Za-z0-9_]+", l):
                    hashtags.append(l)
                if re.search("@[A-Za-z0-9_]+", l):
                    mentions.append(l)
            if len(hashtags) > 0:
                contents.update({HASHTAG_NAME: hashtags})
            if len(mentions) > 0:
                contents.update({MENTIONS_NAME: mentions})
            links = [l for l in links if l not in hashtags + mentions]
            if len(links) > 0:
                contents.update({LINKS_NAME: links})
        text = text.get_text()

        # Datetime and url
        datetime_raw = soup.find("span", class_ = "tweet-date").find("a")
        id = database_wrapper.extract_last_url_element(datetime_raw["href"])
        datetime_unparsed = datetime_raw["title"]
        datetime_utc = datetime.strptime(datetime_unparsed, "%b %d, %Y · %I:%M %p %Z")
        datetime_utc_str = datetime_utc.isoformat()
        contents.update({ID_NAME: id, DATETIME_NAME: datetime_utc_str})

        hash_value = database_wrapper.hash_object(text + datetime_utc_str)

        # Commenter name
        user = soup.find("div", class_ = "tweet-header").find("a", class_ = "fullname")
        contents.update({COMMENTER_NAME_USERNAME: user["href"].replace("/", ""), COMMENTER_NAME_FULLNAME: user.get_text()})

        media_raw = soup.find("div", class_ = "attachments")
        media = []
        if media_raw is not None:
            img = media_raw.find_all("img")
            if len(img) > 0:
                images = [{"media_url": i["src"], "binary_data": requests.get(i["src"]).content} for i in img]
                media.extend(images)
            video = media_raw.find_all("video")
            if len(video) > 0:
                videos = [{"media_url": v.find("source")["src"], "binary_data": requests.get(v.find("source")["src"]).content} for v in video]
                media.extend(videos)
            if len(media) > 0:
                for m in media:
                    if len(bson.BSON.encode(m)) >= BSON_SIZE_LIMIT:
                        m["binary_data"] = "To large to store in database."
                contents.update({MEDIA_NAME: [m["media_url"] for m in media]})
                if ATTACHMENTS: database_wrapper.insert_one_tweet(attachments_con, {ID_NAME: id, MEDIA_NAME: media})
                hash_value = database_wrapper.hash_object(text + datetime_utc_str + str(media))

        contents.update({TEXT_NAME: text, "hash256": hash_value})
        return contents

def parse_arguments():
    parser = argparse.ArgumentParser(description="Web scraper for X (formerly Twitter)")
    
    # Profile parameter (mandatory)
    parser.add_argument("-p", "--profile", required=True, type=str,
                        help="The profile username to scrape. Can be provided with or without '@'.")
    
    # Maximum comments (optional, default: 10)
    parser.add_argument("--max-comments", type=int, default=10,
                        help="The maximum number of comments to scrape per tweet. Default is 10.")
    
    # Attachments flag (optional, default: yes)
    parser.add_argument("--attachments", choices=["yes", "no"], default="yes",
                        help="Whether to scrape tweet attachments as binary files. Default is 'yes'.")
    
    # Waiting time (optional, default: 7)
    parser.add_argument("--waiting-time", type=int, default=7,
                        help="Time period to wait until a new tweet is scraped. Default is 7.")
    
    args = parser.parse_args()
    
    # Clean up profile username
    args.profile = args.profile.lstrip('@')
    
    return args

if __name__ == '__main__':
    try:
        db = database_wrapper.mongo_authenticate('./')['xdb']
        cols = db.list_collection_names()
        attachments_con = db[ATTACHMENTS_DB]
        comments_con = db[COMMENTS_DB]
        tweets_con = db[TWEETS_DB]
        print('Connection working.')
    except Exception as e:
        print('Connection not working.')
        print(e)
        exit(1)

    args = parse_arguments()
    COMMENT_LIMIT = args.max_comments
    if args.attachments == "no":
        ATTACHMENTS = False
    WAITING_TIME_DAYS = args.waiting_time

    profile = args.profile
    profile_url = "https://xcancel.com/" + profile

    timeline_new_entries = []
    timeline_existing_entries = database_wrapper.get_hash_of_all_tweets(tweets_con)

    options = uc.ChromeOptions()
    options.headless = True
    driver = uc.Chrome(options=options)

    driver.get(profile_url)
    sleep(SLEEPER_MIN + random.randint(2,4))

    # Scraping of user tweets
    print("Start scraping profile @" + profile + "...")

    continue_scraping = True
    while continue_scraping:
        timeline = driver.find_elements(By.CLASS_NAME, "timeline-item")
        try:
            load_more_link = driver.find_element(By.LINK_TEXT, "Load more")
        except NoSuchElementException:
            load_more_link = None
            pass

        try:
            no_more_items_h2 = driver.find_element(By.XPATH, "//h2[contains(.,'No more items')]")
        except NoSuchElementException:
            no_more_items_h2 = None
            pass

        if (load_more_link is not None):
            # Parse items
            for tweet in timeline:
                tweet_scraped = parse_timeline_tweet(tweet, timeline_existing_entries)
                if tweet_scraped == -1:
                    continue_scraping = False
                    break
                elif tweet_scraped is not None: timeline_new_entries.append(tweet_scraped)
            if continue_scraping:
                driver.get(load_more_link.get_attribute('href'))
                sleep(SLEEPER_MIN + random.randint(2,4))
        elif (no_more_items_h2 is not None):
            for tweet in timeline:
                tweet_scraped = parse_timeline_tweet(tweet, timeline_existing_entries)
                if tweet_scraped == -1:
                    continue_scraping = False
                    break
                elif tweet_scraped is not None: timeline_new_entries.append(tweet_scraped)
            continue_scraping = False
        else:
            driver.save_screenshot("error.png")
            continue_scraping = False
    
    if len(timeline_new_entries) > 0:
        database_wrapper.insert_new_tweets(tweets_con, timeline_new_entries)
    else:
         print("Scraping completed. No new tweets.")
         exit(0)

    print("Scraping finished, obtained " + str(len(timeline_new_entries)) + " new tweets.")

    print("Start scraping tweets...")

    # Scraping of tweet replies

    for tweet in timeline_new_entries:
        link = profile_url + "/status/" + tweet[ID_NAME]
        driver.get(link)
        sleep(SLEEPER_MIN + random.randint(2,4))

        print("Scraping " + link + "...")

        conversation_entries = []

        continue_scraping = True
        while continue_scraping:
            conversation = driver.find_elements(By.CLASS_NAME, "reply")

            try:
                load_more_link = driver.find_element(By.LINK_TEXT, "Load more")
            except NoSuchElementException:
                load_more_link = None
                pass

            try:
                no_more_items_h2 = driver.find_element(By.XPATH, "//h2[contains(.,'No more items')]")
            except NoSuchElementException:
                no_more_items_h2 = None
                pass

            if (load_more_link is not None):
                # Parse items
                for reply in conversation:
                    reply_scraped = parse_conversation_tweet(reply)
                    conversation_entries.append(reply_scraped)
                    if len(conversation_entries) >= COMMENT_LIMIT:
                        continue_scraping = False
                        break
                if continue_scraping:
                    driver.get(load_more_link.get_attribute('href'))
                    sleep(SLEEPER_MIN + random.randint(2,4))
            elif (no_more_items_h2 is not None):
                for reply in conversation:
                    reply_scraped = parse_conversation_tweet(reply)
                    conversation_entries.append(reply_scraped)
                continue_scraping = False
            else:
                driver.save_screenshot("error.png")
                continue_scraping = False

        if len(conversation_entries) > 0:
            database_wrapper.insert_new_tweets(comments_con, conversation_entries)
    
        print("Scraping of tweet " + tweet[ID_NAME] + " finished, obtained " + str(len(conversation_entries)) + " comments.")
    
    print("Scraping of tweets and comments completed.")