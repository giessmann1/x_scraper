import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import requests
import bson
import re
from typing import Any, Dict, List, Optional, Union
import argparse
import random
from time import sleep
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from database_wrapper import (
    mongo_authenticate,
    insert_one_tweet,
    get_hash_of_all_tweets,
    extract_last_url_element,
    hash_object
)

# Constants
STATS_LEGEND = ["replies", "reposts", "quotes", "likes", "views_video"]
BSON_SIZE_LIMIT = 16793600
ATTACHMENTS_DB = "attachments"
COMMENTS_DB = "comments"
TWEETS_DB = "tweets"
SLEEPER_MIN = 10
ID_NAME = "id"
SLEEP_INTERVAL = lambda: random.randint(2, 4)

# Field Names
ID_NAME = "id"
DATETIME_NAME = "datetime_utc"
LINKS_NAME = "links"
MEDIA_NAME = "attachments"
TEXT_NAME = "text"
IS_REPOST = "is_repost"
HASHTAG_NAME = "hashtags"
MENTIONS_NAME = "mentions"
TWEET_ID_NAME = "ref_tweet_id"
QUOTE_NAME = "quote"


def us_number_to_int(string: str) -> int:
    """Converts US-style formatted numbers to integers."""
    string_transformed = string.strip().replace(",", "")
    return 0 if string_transformed in ["GIF", ""] else int(string_transformed)


def extract_tweet_metadata(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
    """Extracts metadata such as stats, hashtags, mentions, and links from a tweet."""
    contents: Dict[str, Any] = {}
    stats_raw = soup.find_all("span", class_="tweet-stat")
    
    if not stats_raw:
        return None

    for idx, stat in enumerate(stats_raw):
        try:
            contents[STATS_LEGEND[idx]] = us_number_to_int(stat.getText())
        except (ValueError, IndexError):
            print("Error parsing tweet stats: ", soup.prettify())
    
    text_div = soup.find("div", class_="tweet-content")
    if not text_div:
        return None
    
    links = [l.getText() for l in text_div.find_all("a")]
    contents[HASHTAG_NAME] = [l for l in links if re.search("#[A-Za-z0-9_]+", l)]
    contents[MENTIONS_NAME] = [l for l in links if re.search("@[A-Za-z0-9_]+", l)]
    contents[LINKS_NAME] = [l for l in links if l not in contents[HASHTAG_NAME] + contents[MENTIONS_NAME]]
    contents[TEXT_NAME] = text_div.get_text()
    
    return contents


def extract_datetime_and_id(soup: BeautifulSoup) -> Optional[Dict[str, str]]:
    """Extracts tweet ID and UTC datetime from a tweet."""
    datetime_raw = soup.find("span", class_="tweet-date").find("a")
    if not datetime_raw:
        return None
    
    tweet_id = extract_last_url_element(datetime_raw["href"])
    datetime_utc = datetime.strptime(datetime_raw["title"], "%b %d, %Y · %I:%M %p %Z").isoformat()
    
    return {ID_NAME: tweet_id, DATETIME_NAME: datetime_utc}


def extract_user_info(soup: BeautifulSoup, class_name: str) -> Dict[str, str]:
    """Extracts user information (username and fullname)."""
    user_info = {}
    user_raw = soup.find("div", class_=class_name).find("a", class_="fullname")
    
    if user_raw:
        user_info["username"] = user_raw["href"].replace("/", "")
        user_info["fullname"] = user_raw.get_text()
    
    return user_info


def extract_media(soup: BeautifulSoup) -> List[Dict[str, Union[str, bytes]]]:
    """Extracts media (images/videos) from a tweet."""
    media_list = []
    media_raw = soup.find("div", class_="attachments")
    
    if media_raw:
        for img in media_raw.find_all("img"):
            media_url = img["src"]
            media_list.append({"media_url": media_url, "binary_data": requests.get(media_url).content})

        for video in media_raw.find_all("video"):
            video_url = video.find("source")["src"]
            media_list.append({"media_url": video_url, "binary_data": requests.get(video_url).content})

        for media in media_list:
            if len(bson.BSON.encode(media)) >= BSON_SIZE_LIMIT:
                media["binary_data"] = "Too large to store in database."
    
    return media_list


def extract_quote(soup: BeautifulSoup, attachments_con: Any, attachments: bool) -> Optional[Dict[str, Any]]:
    """Extracts quoted tweet information."""
    quote_raw = soup.find("div", class_="quote")
    if not quote_raw:
        return None
    
    quote_contents = {}
    quote_contents.update({f"{QUOTE_NAME}_{TEXT_NAME}": quote_raw.find("div", class_="quote-text").get_text()})

    user_info = extract_user_info(quote_raw, "tweet-name-row")
    if user_info:
        quote_contents.update({f"{QUOTE_NAME}_{k}": v for k, v in user_info.items()})

    datetime_data = extract_datetime_and_id(quote_raw)
    if datetime_data:
        quote_contents.update({f"{QUOTE_NAME}_{k}": v for k, v in datetime_data.items()})

    media = extract_media(soup)
    if media and attachments:
        quote_contents[f"{QUOTE_NAME}_{MEDIA_NAME}"] = [m["media_url"] for m in media]
        insert_one_tweet(attachments_con, {TWEET_ID_NAME: quote_contents[f"{QUOTE_NAME}_{ID_NAME}"], MEDIA_NAME: media, QUOTE_NAME: True})
    
    return quote_contents


def parse_tweet(soup: BeautifulSoup, existing_entries: list, attachments_con: Any, is_profile_tweet: bool, waiting_time_days: int, attachments: bool) -> Optional[Union[Dict[str, Any], int]]:
    """Tweet parsing function for both timeline and conversation tweets."""
    contents = extract_tweet_metadata(soup)
    if contents is None:
        return None
    
    datetime_data = extract_datetime_and_id(soup)
    if datetime_data is None:
        return None
    
    contents.update(datetime_data)
    contents.update(extract_user_info(soup, "tweet-header"))
    
    tweet_hash = hash_object(contents[TEXT_NAME] + contents[DATETIME_NAME])
    if tweet_hash in existing_entries:
        print("Tweet already scraped.")
        return -1
    contents["hash256"] = tweet_hash
    
    if is_profile_tweet and datetime.now() - datetime.fromisoformat(contents[DATETIME_NAME]) <= timedelta(days = waiting_time_days):
        print("Tweet not old enough to be scraped, skipping.")
        return None
    
    contents[IS_REPOST] = soup.find("div", class_="retweet-header") is not None
    
    quote = extract_quote(soup, attachments_con, attachments)
    if quote:
        contents.update(quote)

    media = extract_media(soup)
    if media and attachments:
        media_list = [m["media_url"] for m in media]
        remaining_attachments = set(media_list) - set(quote[f"{QUOTE_NAME}_{MEDIA_NAME}"])
        if len(remaining_attachments) > 0:
            contents[MEDIA_NAME] = remaining_attachments
            insert_one_tweet(attachments_con, {TWEET_ID_NAME: contents[ID_NAME], MEDIA_NAME: [m for m in media if m["media_url"] in remaining_attachments]})

    return contents


def setup_driver() -> WebDriver:
    """Initialize and return a Chrome WebDriver."""
    options = uc.ChromeOptions()
    options.headless = True
    return uc.Chrome(use_subprocess=True, options=options, version_main=112)


def setup_database() -> Dict[str, Any]:
    """Establishes a connection to the MongoDB database."""
    try:
        db = mongo_authenticate("./")["xdb"]
        return {
            "attachments": db[ATTACHMENTS_DB],
            "comments": db[COMMENTS_DB],
            "tweets": db[TWEETS_DB],
        }
    except Exception as e:
        print("Database connection failed:", e)
        exit(1)


def tweet_url(profile_url: str, tweet_id: str) -> str:
    return f"{profile_url}/status/{tweet_id}"


def scrape_tweets(driver: WebDriver, url: str, db_collections: Any, force_rescrape: str, max_items: int, is_profile: bool, waiting_time_days: int, attachments: bool) -> List[str]:
    """Generic function to scrape tweets from a profile or a conversation thread."""
    print(f"Scraping {url}...")
    driver.get(url)
    sleep(SLEEPER_MIN + SLEEP_INTERVAL())
    
    db_key = TWEETS_DB if is_profile else COMMENTS_DB

    # Rescraping logic
    if is_profile and force_rescrape in ["both", "tweets"]:
        existing_entries = list()
    elif not is_profile and force_rescrape in ["both", "comments"]:
        existing_entries = list()
    else:
        existing_entries = get_hash_of_all_tweets(db_collections[db_key])
        
    new_tweet_ids = []
    tweet_class = "timeline-item" if is_profile else "reply"
    ref_tweet_id = url.split('/')[-1] if not is_profile else None
    
    while True:
        timeline = driver.find_elements(By.CLASS_NAME, tweet_class)
        
        for tweet in timeline:
            try:
                tweet_body = tweet.find_element(By.TAG_NAME, "div")
                tweet_soup = BeautifulSoup(tweet_body.get_attribute("outerHTML"), "html.parser")
                tweet_data = parse_tweet(tweet_soup, existing_entries, db_collections[ATTACHMENTS_DB], is_profile, waiting_time_days, attachments)
                
                if tweet_data == -1:
                    print(f"Scraped {len(new_tweet_ids)} new {'tweets' if is_profile else 'comments'}.")
                    return new_tweet_ids  # Stop scraping
                elif tweet_data:
                    if ref_tweet_id: tweet_data.update({TWEET_ID_NAME: ref_tweet_id})
                    insert_one_tweet(db_collections[db_key], tweet_data)
                    new_tweet_ids.append(tweet_data[ID_NAME])
                
                if len(new_tweet_ids) >= max_items:
                    print(f"Scraped {len(new_tweet_ids)} new {'tweets' if is_profile else 'comments'}.")
                    return new_tweet_ids  # Stop if max tweets reached
            except NoSuchElementException:
                continue  # Ignore non-tweet elements
        
        # Handle pagination
        if (load_more := driver.find_elements(By.LINK_TEXT, "Load more")):
            driver.get(load_more[0].get_attribute('href'))
            sleep(SLEEPER_MIN + SLEEP_INTERVAL())
        elif driver.find_elements(By.XPATH, "//h2[contains(.,'No more items')]"):
            break
        else:
            driver.save_screenshot("error.png")
            break
    
    print(f"Scraped {len(new_tweet_ids)} new {'tweets' if is_profile else 'comments'}.")
    return new_tweet_ids


def str_to_bool(value):
    if isinstance(value, bool):
        return value
    if value.lower() in ('true', 'yes', 'y', '1'):
        return True
    elif value.lower() in ('false', 'no', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Web scraper for X (formerly Twitter)")
    parser.add_argument("-p", "--profile", required=True, type=str, help="Profile username to scrape.")
    parser.add_argument("-t", "--tweet", type=str, default=None, help="Status ID of a single tweet to scrape.")
    parser.add_argument("--max-comments", type=int, default=10, help="Maximum number of comments per tweet.")
    parser.add_argument("--max-tweets", type=int, default=10, help="Maximum number of tweets in profile to scrape.")
    parser.add_argument("--attachments", type=str_to_bool, default="yes", help="Scrape attachments.")
    parser.add_argument("--waiting-time", type=int, default=7, help="Time to wait before scraping new tweets.")
    parser.add_argument(
    "-f", "--force",
    choices=["both", "tweets", "comments", "none"],
    default="none",
    help="Force rescraping: 'both' for tweets and comments, 'tweets' for tweets only, 'comments' for comments only, 'none' for no force."
)
    # parser.add_argument("--deep", action="store_true", help="Scrape comments of comments.")
    
    args = parser.parse_args()
    args.profile = args.profile.lstrip('@')  # Remove '@' if provided
    return args


def main() -> None:
    """Main function to manage the scraping process."""
    args = parse_arguments()
    db_collections = setup_database()
    driver = setup_driver()

    profile_url = f"https://xcancel.com/{args.profile}"
    
    if args.tweet:
        scrape_tweets(driver, tweet_url(profile_url, args.tweet), db_collections, args.force, 1, True, 0, args.attachments)
        if args.max_comments > 0:
            scrape_tweets(driver, tweet_url(profile_url, args.tweet), db_collections, args.force, args.max_comments, False, 0, args.attachments)
    else:
        new_tweets = scrape_tweets(driver, profile_url, db_collections, args.force, args.max_tweets, True, args.waiting_time, args.attachments)
        if new_tweets and args.max_comments > 0:
            for tweet in new_tweets:
                scrape_tweets(driver, tweet_url(profile_url, tweet), db_collections, args.force, args.max_comments, False, args.waiting_time, args.attachments)
    
    print("Scraping completed.")
    driver.quit()

if __name__ == '__main__':
    main()
