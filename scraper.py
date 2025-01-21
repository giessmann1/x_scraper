import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
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
WAITING_TIME_DAYS = 7
USER_NAME_USERNAME = "profile_username"
USER_NAME_FULLNAME = "profile_fullname"
IS_REPOST = "is_repost"
COMMENTER_NAME_USERNAME = "commenter_username"
COMMENTER_NAME_FULLNAME = "commenter_fullname"
COMMENT_LIMIT = 10
SLEEPER_MIN = 15
BSON_SIZE_LIMIT = 16793600
HASHTAG_NAME = "hashtags"
MENTIONS_NAME = "mentions"
ATTACHMENTS_DB = "attachments"
COMMENTS_DB = "comments"
TWEETS_DB = "tweets"
ATTACHMENTS = True


def us_number_to_int(string):
    string_transformed = string.strip().replace(",", "")
    return 0 if string_transformed in ["GIF", ""] else int(string_transformed)


def parse_tweet_common(soup):
    contents = {}
    stats_raw = soup.find_all("span", class_="tweet-stat")
    if not stats_raw:
        return None

    for ids, s in enumerate(stats_raw):
        try:
            contents[STATS_LEGEND[ids]] = us_number_to_int(s.getText())
        except:
            print("Error parsing tweet stats: " + soup.prettify())
        
    text = soup.find("div", class_="tweet-content")
    links = [l.getText() for l in text.find_all("a")]
    hashtags = [l for l in links if re.search("#[A-Za-z0-9_]+", l)]
    mentions = [l for l in links if re.search("@[A-Za-z0-9_]+", l)]
    links = [l for l in links if l not in hashtags + mentions]

    if hashtags:
        contents[HASHTAG_NAME] = hashtags
    if mentions:
        contents[MENTIONS_NAME] = mentions
    if links:
        contents[LINKS_NAME] = links

    contents[TEXT_NAME] = text.get_text()
    return contents


def parse_timeline_tweet(tweet, existing_entries):
    soup = BeautifulSoup(tweet.get_attribute("outerHTML"), "html.parser")
    contents = parse_tweet_common(soup)
    if contents is None:
        return None

    datetime_raw = soup.find("span", class_="tweet-date").find("a")
    id = database_wrapper.extract_last_url_element(datetime_raw["href"])
    datetime_unparsed = datetime_raw["title"]
    datetime_utc = datetime.strptime(
        datetime_unparsed, "%b %d, %Y · %I:%M %p %Z")
    datetime_utc_str = datetime_utc.isoformat()

    hash_value = database_wrapper.hash_object(
        contents[TEXT_NAME] + datetime_utc_str)
    if hash_value in existing_entries:
        print("Tweet already scraped.")
        return -1

    if datetime.now() - datetime_utc < timedelta(days=WAITING_TIME_DAYS):
        print("Tweet not old enough to be scraped, skip.")
        return None

    contents.update({ID_NAME: id, DATETIME_NAME: datetime_utc_str})
    contents[IS_REPOST] = soup.find("div", class_="retweet-header") is not None

    user_raw = soup.find(
        "div", class_="tweet-header").find("a", class_="fullname")
    contents.update({USER_NAME_USERNAME: user_raw["href"].replace(
        "/", ""), USER_NAME_FULLNAME: user_raw.get_text()})

    media_raw = soup.find("div", class_="attachments")
    if media_raw:
        media = []
        for img in media_raw.find_all("img"):
            media.append(
                {"media_url": img["src"], "binary_data": requests.get(img["src"]).content})
        for video in media_raw.find_all("video"):
            media.append({"media_url": video.find("source")[
                         "src"], "binary_data": requests.get(video.find("source")["src"]).content})

        for m in media:
            if len(bson.BSON.encode(m)) >= BSON_SIZE_LIMIT:
                m["binary_data"] = "Too large to store in database."
        contents[MEDIA_NAME] = [m["media_url"] for m in media]
        if ATTACHMENTS:
            database_wrapper.insert_one_tweet(
                attachments_con, {ID_NAME: id, MEDIA_NAME: media})
        hash_value = database_wrapper.hash_object(
            contents[TEXT_NAME] + datetime_utc_str + str(media))
        if hash_value in existing_entries:
            print("Tweet already scraped.")
            return -1

    contents["hash256"] = hash_value
    return contents


def parse_conversation_tweet(reply):
    soup = BeautifulSoup(reply.get_attribute("outerHTML"), "html.parser")
    contents = parse_tweet_common(soup)
    if contents is None:
        return None

    datetime_raw = soup.find("span", class_="tweet-date").find("a")
    id = database_wrapper.extract_last_url_element(datetime_raw["href"])
    datetime_unparsed = datetime_raw["title"]
    datetime_utc = datetime.strptime(
        datetime_unparsed, "%b %d, %Y · %I:%M %p %Z")
    datetime_utc_str = datetime_utc.isoformat()

    contents.update({ID_NAME: id, DATETIME_NAME: datetime_utc_str})
    contents["hash256"] = database_wrapper.hash_object(
        contents[TEXT_NAME] + datetime_utc_str)

    user = soup.find("div", class_="tweet-header").find("a", class_="fullname")
    contents.update({COMMENTER_NAME_USERNAME: user["href"].replace(
        "/", ""), COMMENTER_NAME_FULLNAME: user.get_text()})

    media_raw = soup.find("div", class_="attachments")
    if media_raw:
        media = []
        for img in media_raw.find_all("img"):
            media.append(
                {"media_url": img["src"], "binary_data": requests.get(img["src"]).content})
        for video in media_raw.find_all("video"):
            media.append({"media_url": video.find("source")[
                         "src"], "binary_data": requests.get(video.find("source")["src"]).content})

        for m in media:
            if len(bson.BSON.encode(m)) >= BSON_SIZE_LIMIT:
                m["binary_data"] = "Too large to store in database."
        contents[MEDIA_NAME] = [m["media_url"] for m in media]
        if ATTACHMENTS:
            database_wrapper.insert_one_tweet(
                attachments_con, {ID_NAME: id, MEDIA_NAME: media})
        contents["hash256"] = database_wrapper.hash_object(
            contents[TEXT_NAME] + datetime_utc_str + str(media))

    return contents


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Web scraper for X (formerly Twitter)")
    parser.add_argument("-p", "--profile", required=True, type=str,
                        help="The profile username to scrape. Can be provided with or without '@'.")
    parser.add_argument("-t", "--tweet", type=str, default=None,
                        help="The status id of a single tweet to be scraped.")
    parser.add_argument("--max-comments", type=int, default=10,
                        help="The maximum number of comments to scrape per tweet. Default is 10.")
    parser.add_argument("--attachments", choices=["yes", "no"], default="yes",
                        help="Whether to scrape tweet attachments as binary files. Default is 'yes'.")
    parser.add_argument("--waiting-time", type=int, default=7,
                        help="Time period to wait until a new tweet is scraped. Default is 7.")
    args = parser.parse_args()
    args.profile = args.profile.lstrip('@')
    return args


if __name__ == '__main__':
    try:
        db = database_wrapper.mongo_authenticate('./')['xdb']
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
    ATTACHMENTS = args.attachments == "yes"
    WAITING_TIME_DAYS = args.waiting_time

    profile = args.profile
    profile_url = f"https://xcancel.com/{profile}"

    tweet_id = args.tweet

    chrome_options = uc.ChromeOptions()
    chrome_options.headless = True

    driver = uc.Chrome(use_subprocess=True, options=chrome_options, version_main=112)

    if tweet_id is None: # Scrape entire profile
    
        print(f"Start scraping profile @{profile}...")

        timeline_new_entries = []
        timeline_existing_entries = database_wrapper.get_hash_of_all_tweets(tweets_con)

        driver.get(profile_url)
        sleep(SLEEPER_MIN + random.randint(2, 4))

        continue_scraping = True
        while continue_scraping:
            timeline = driver.find_elements(By.CLASS_NAME, "timeline-item")
            load_more_link = driver.find_element(By.LINK_TEXT, "Load more") if driver.find_elements(
                By.LINK_TEXT, "Load more") else None
            no_more_items_h2 = driver.find_element(By.XPATH, "//h2[contains(.,'No more items')]") if driver.find_elements(
                By.XPATH, "//h2[contains(.,'No more items')]") else None

            if load_more_link:
                for tweet in timeline:
                    tweet_scraped = parse_timeline_tweet(
                        tweet, timeline_existing_entries)
                    if tweet_scraped == -1:
                        continue_scraping = False
                        break
                    elif tweet_scraped:
                        timeline_new_entries.append(tweet_scraped)
                if continue_scraping:
                    driver.get(load_more_link.get_attribute('href'))
                    sleep(SLEEPER_MIN + random.randint(2, 4))
            elif no_more_items_h2:
                for tweet in timeline:
                    tweet_scraped = parse_timeline_tweet(
                        tweet, timeline_existing_entries)
                    if tweet_scraped == -1:
                        continue_scraping = False
                        break
                    elif tweet_scraped:
                        timeline_new_entries.append(tweet_scraped)
                continue_scraping = False
            else:
                driver.save_screenshot("error.png")
                continue_scraping = False

        if timeline_new_entries:
            database_wrapper.insert_new_tweets(tweets_con, timeline_new_entries)
        else:
            print("Scraping completed. No new tweets.")
            exit(0)

        print(f"Scraping finished, obtained {
            len(timeline_new_entries)} new tweets.")

        print("Start scraping tweets...")

        for tweet in timeline_new_entries:
            link = f"{profile_url}/status/{tweet[ID_NAME]}"
            driver.get(link)
            sleep(SLEEPER_MIN + random.randint(2, 4))

            print(f"Scraping {link}...")

            conversation_entries = []
            continue_scraping = True
            while continue_scraping:
                conversation = driver.find_elements(By.CLASS_NAME, "reply")
                load_more_link = driver.find_element(By.LINK_TEXT, "Load more") if driver.find_elements(
                    By.LINK_TEXT, "Load more") else None
                icon_down_a = driver.find_element(By.XPATH, "//a[@class='icon-down']") if driver.find_elements(
                    By.XPATH, "//a[@class='icon-down']") else None

                if load_more_link:
                    for reply in conversation:
                        reply_scraped = parse_conversation_tweet(reply)
                        conversation_entries.append(reply_scraped)
                        if len(conversation_entries) >= COMMENT_LIMIT:
                            continue_scraping = False
                            break
                    if continue_scraping:
                        driver.get(load_more_link.get_attribute('href'))
                        sleep(SLEEPER_MIN + random.randint(2, 4))
                elif icon_down_a:
                    for reply in conversation:
                        reply_scraped = parse_conversation_tweet(reply)
                        conversation_entries.append(reply_scraped)
                    continue_scraping = False
                else:
                    driver.save_screenshot("error.png")
                    continue_scraping = False

            if conversation_entries:
                database_wrapper.insert_new_tweets(
                    comments_con, conversation_entries)

            print(f"Scraping of tweet {tweet[ID_NAME]} finished, obtained {
                len(conversation_entries)} comments.")

        print("Scraping of tweets and comments completed.")
    
    else: # Scrape single tweet

        link = f"{profile_url}/status/{tweet_id}"
        driver.get(link)
        sleep(SLEEPER_MIN + random.randint(2, 4))

        print(f"Scraping {link}...")

        conversation_entries = []
        continue_scraping = True
        while continue_scraping:
            conversation = driver.find_elements(By.CLASS_NAME, "reply")
            load_more_link = driver.find_element(By.LINK_TEXT, "Load more") if driver.find_elements(
                By.LINK_TEXT, "Load more") else None
            icon_down_a = driver.find_element(By.XPATH, "//a[@class='icon-down']") if driver.find_elements(
                By.XPATH, "//a[@class='icon-down']") else None

            if load_more_link:
                for reply in conversation:
                    reply_scraped = parse_conversation_tweet(reply)
                    conversation_entries.append(reply_scraped)
                    if len(conversation_entries) >= COMMENT_LIMIT:
                        continue_scraping = False
                        break
                if continue_scraping:
                    driver.get(load_more_link.get_attribute('href'))
                    sleep(SLEEPER_MIN + random.randint(2, 4))
            elif icon_down_a:
                for reply in conversation:
                    reply_scraped = parse_conversation_tweet(reply)
                    conversation_entries.append(reply_scraped)
                continue_scraping = False
            else:
                driver.save_screenshot("error.png")
                continue_scraping = False

        if conversation_entries:
            database_wrapper.insert_new_tweets(
                comments_con, conversation_entries)

        print(f"Scraping of tweet {tweet_id} finished, obtained {
            len(conversation_entries)} comments.")
