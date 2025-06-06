import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import requests
import re
from typing import Any, Dict, List, Optional, Union
import argparse
import random
from time import sleep
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from pymongo.errors import DocumentTooLarge, WriteError
from database_wrapper import (
    mongo_authenticate,
    insert_one_tweet,
    get_hash_of_all_tweets,
    extract_last_url_element,
    hash_object,
    get_tweet_by_username
)

# Constants
STATS_LEGEND = ["replies_int", "reposts_int", "quotes_int", "likes_int", "views_video_int"]
ATTACHMENTS_DB = "attachments"
COMMENTS_DB = "comments"
TWEETS_DB = "tweets"
PROFILE_DB = "profile"
SLEEPER_MIN = 10
SLEEP_INTERVAL = lambda: random.randint(2, 4)
MAX_DEPTH = 9999
MAX_ATTEMPTS = 3

# Field Names
ID_NAME = "tweet_id_str"
DATETIME_NAME = "datetime_utc_iso"
LINKS_NAME = "links_list"
MEDIA_NAME = "attachments_list"
TEXT_NAME = "text_str"
IS_REPOST = "is_repost_bool"
HASHTAG_NAME = "hashtags_list"
MENTIONS_NAME = "mentions_list"
TWEET_ID_NAME = "ref_tweet_id_str"
PROFILE_TWEET_ID_NAME = "profile_tweet_id_str"
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
        user_info["username_str"] = user_raw["href"].replace("/", "")
        user_info["fullname_str"] = user_raw.get_text()
    
    return user_info


def extract_media(soup: BeautifulSoup) -> List[Dict[str, Union[str, bytes]]]:
    """Extracts media (images/videos) from a tweet."""
    media_list = []
    media_raw = soup.find("div", class_="attachments")
    
    if media_raw:
        for img in media_raw.find_all("img"):
            media_url = img["src"]
            media_list.append({"media_url_str": media_url, "binary_data_bytes": requests.get(media_url).content})

        for video in media_raw.find_all("video"):
            video_url = video.find("source")["src"]
            media_list.append({"media_url_str": video_url, "binary_data_bytes": requests.get(video_url).content})
    
    return media_list


def extract_quote(soup: BeautifulSoup, attachments_con: Any, attachments: bool) -> Optional[Dict[str, Any]]:
    """Extracts quoted tweet information."""
    quote_raw = soup.find("div", class_="quote")
    if not quote_raw:
        return None
    
    quote_contents = {}
    quote_text = quote_raw.find("div", class_="quote-text")
    if not quote_text:
        return None
    quote_contents.update({f"{QUOTE_NAME}_{TEXT_NAME}": quote_text.get_text()})

    user_info = extract_user_info(quote_raw, "tweet-name-row")
    if user_info:
        quote_contents.update({f"{QUOTE_NAME}_{k}": v for k, v in user_info.items()})

    datetime_data = extract_datetime_and_id(quote_raw)
    if datetime_data:
        quote_contents.update({f"{QUOTE_NAME}_{k}": v for k, v in datetime_data.items()})

    media = extract_media(soup)
    if media and attachments:
        quote_contents[f"{QUOTE_NAME}_{MEDIA_NAME}"] = [m["media_url_str"] for m in media]
        try:
            insert_one_tweet(attachments_con, {TWEET_ID_NAME: quote_contents[f"{QUOTE_NAME}_{ID_NAME}"], MEDIA_NAME: media, f"{QUOTE_NAME}_bool": True})
        except (DocumentTooLarge, WriteError):
            insert_one_tweet(attachments_con, {TWEET_ID_NAME: quote_contents[f"{QUOTE_NAME}_{ID_NAME}"], MEDIA_NAME: "Too large to store in database.", f"{QUOTE_NAME}_bool": True})
            print("Media too large to store in database, skipping.")
    
    return quote_contents


def parse_tweet(soup: BeautifulSoup, existing_entries: list, attachments_con: Any, is_profile_tweet: bool, waiting_time_days: int, attachments: bool, profile_info: dict = None) -> Optional[Union[Dict[str, Any], int]]:
    """Tweet parsing function for both timeline and conversation tweets."""
    contents = extract_tweet_metadata(soup)
    if contents is None:
        return None
    
    datetime_data = extract_datetime_and_id(soup)
    if datetime_data is None:
        return None
    contents.update(datetime_data)

    user_info = extract_user_info(soup, "tweet-header")
    if user_info is None:
        return None
    contents.update(user_info)
    
    tweet_hash = hash_object(contents[TEXT_NAME] + contents[DATETIME_NAME] + contents["username_str"])
    if tweet_hash in existing_entries:
        print("Tweet already scraped.")
        return -1
    contents["hash256_str"] = tweet_hash
    
    if is_profile_tweet and datetime.now() - datetime.fromisoformat(contents[DATETIME_NAME]) <= timedelta(days = waiting_time_days):
        print("Tweet not old enough to be scraped, skipping.")
        return None
    
    if is_profile_tweet:
        contents[IS_REPOST] = soup.find("div", class_="retweet-header") is not None
        if contents[IS_REPOST]:
            # In this case the retrieved username and fullname are for the original tweet
            contents["username_str"] = profile_info["username_str"]
            contents["fullname_str"] = profile_info["fullname_str"]
            contents["repost_username_str"] = user_info["username_str"]
            contents["repost_fullname_str"] = user_info["fullname_str"]

    
    quote = extract_quote(soup, attachments_con, attachments)
    if quote:
        contents.update(quote)

    if attachments:
        media = extract_media(soup)
        if media:
            media_list = [m["media_url_str"] for m in media]
            if quote:
                remaining_attachments = set(media_list) - set(quote[f"{QUOTE_NAME}_{MEDIA_NAME}"])
                if len(remaining_attachments) > 0:
                    contents[MEDIA_NAME] = remaining_attachments
                    try:
                        insert_one_tweet(attachments_con, {TWEET_ID_NAME: contents[ID_NAME], MEDIA_NAME: [m for m in media if m["media_url_str"] in remaining_attachments]})
                    except (DocumentTooLarge, WriteError):
                        insert_one_tweet(attachments_con, {TWEET_ID_NAME: contents[ID_NAME], MEDIA_NAME: "Too large to store in database."})
                        print("Media too large to store in database, skipping.")
            else:
                contents[MEDIA_NAME] = media_list
                try:
                    insert_one_tweet(attachments_con, {TWEET_ID_NAME: contents[ID_NAME], MEDIA_NAME: media})
                except (DocumentTooLarge, WriteError):
                    insert_one_tweet(attachments_con, {TWEET_ID_NAME: contents[ID_NAME], MEDIA_NAME: "Too large to store in database."})
                    print("Media too large to store in database, skipping.")
    return contents


def scrape_profile_info(soup: BeautifulSoup) -> Dict[str, str]:
    """Scrapes profile information and stats."""
    try:
        # Bad if those don't exist
        fullname = soup.find("a", class_="profile-card-fullname").get_text()
        username = soup.find("a", class_="profile-card-username").get_text().replace("@", "")
        joindate = soup.find("div", class_="profile-joindate").find("span")["title"]
        joindate = datetime.strptime(joindate, "%I:%M %p - %d %b %Y").isoformat()
        tweets = us_number_to_int(soup.find("li", class_="posts").find("span", class_="profile-stat-num").get_text())
        following = us_number_to_int(soup.find("li", class_="following").find("span", class_="profile-stat-num").get_text())
        followers = us_number_to_int(soup.find("li", class_="followers").find("span", class_="profile-stat-num").get_text())
        likes = us_number_to_int(soup.find("li", class_="likes").find("span", class_="profile-stat-num").get_text())
        verified = soup.find("span", class_="verified-icon")
        if verified:
            verified = True
        else:
            verified = False

        # Optional fields
        profile_bio = soup.find("div", class_="profile-bio")
        if profile_bio:
            profile_bio = profile_bio.get_text().strip()
        else:
            profile_bio = None

        profile_location = soup.find("div", class_="profile-location")
        if profile_location:
            profile_location = profile_location.get_text().strip()
        else:
            profile_location = None

        profile_website = soup.find("div", class_="profile-website")
        if profile_website:
            profile_website = profile_website.find("a")["href"]
        else:
            profile_website = None

        return({"fullname_str": fullname, "username_str": username, "joindate_utc_iso": joindate, "tweets_int": tweets, "following_int": following, "followers_int": followers, "likes_int": likes, "verified_bool": verified, "bio_str": profile_bio, "location_str": profile_location, "website_str": profile_website})
    except NoSuchElementException:
        return None


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
            "profile": db[PROFILE_DB],
        }
    except Exception as e:
        print("Database connection failed:", e)
        exit(1)


def tweet_url(profile_url: str, tweet_id: str) -> str:
    return f"{profile_url}/status/{tweet_id}"


def scrape_tweets(driver: WebDriver, url: str, db_collections: Any, force_rescrape: str, max_items: int, is_profile: bool, waiting_time_days: int, attachments: bool, depth: int = None, profile_tweet: str = None) -> List[str]:
    """Generic function to scrape tweets from a profile or a conversation thread."""
    print(f"Scraping profile {url}...") if is_profile else print(f"Scraping tweet {url}...")

    db_key = TWEETS_DB if is_profile else COMMENTS_DB

    # Rescraping logic
    if is_profile and force_rescrape in ["both", "tweets"]:
        existing_entries = list()
        allow_profile_scrape = True
    elif not is_profile and force_rescrape in ["both", "comments"]:
        existing_entries = list()
    else:
        if is_profile:
            existing_entries = get_hash_of_all_tweets(db_collections[db_key], extract_last_url_element(url))
            profile_info = get_tweet_by_username(db_collections[PROFILE_DB], extract_last_url_element(url))
            if profile_info:
                allow_profile_scrape = False
            else:
                allow_profile_scrape = True
        else:
            existing_entries = get_hash_of_all_tweets(db_collections[db_key])
        
    tweets_with_replies = []
    tweet_counter = 0
    tweet_class = "timeline-item" if is_profile else "reply"

    for attempt in range(MAX_ATTEMPTS):
        if attempt > 0:  # Only show attempt message for retries
            print(f"Attempt {attempt + 1} of {MAX_ATTEMPTS}")

        # Handle error pages
        try:
            driver.get(url)
            sleep(SLEEPER_MIN + SLEEP_INTERVAL())
            if "429 Too Many Requests" in driver.page_source:
                print("Rate limit reached.")
                if attempt < MAX_ATTEMPTS - 1:  # Only sleep if we're going to retry
                    print(f"Retrying in 120 seconds...")
                    sleep(120 + SLEEP_INTERVAL())
                continue # Next attempt
            else:
                error_panel = driver.find_elements(By.CLASS_NAME, "error-panel")
                if error_panel:
                    error_panel_soup = BeautifulSoup(error_panel.get_attribute("outerHTML"), "html.parser")
                    error_text = error_panel_soup.get_text()
                    if error_text == "Page not found":
                        print("Page not found.")
                        return None
                    else:
                        print(f"Error: {error_text}")
                        return None
                # Check for "No items found" message
                no_items = driver.find_elements(By.XPATH, "//h2[contains(text(), 'No items found')]")
                if no_items:
                    print("No tweets found for this profile.")
                    return None
                # else continue as usual
        except Exception as e:
            # Handle other errors (e.g., network issues)
            print(f"Error: {e}")
            driver.save_screenshot("error.png")
            if attempt < MAX_ATTEMPTS - 1:  # Only retry if we haven't hit max attempts
                continue
            return None

        # Store profile info
        if is_profile and allow_profile_scrape:
            try:
                profile_info_src = driver.find_element(By.CLASS_NAME, "profile-card")
                profile_info_src = BeautifulSoup(profile_info_src.get_attribute("outerHTML"), "html.parser")
                if profile_info_src:
                    profile_info = scrape_profile_info(profile_info_src)
                    if profile_info:
                        insert_one_tweet(db_collections[PROFILE_DB], profile_info)
                    else:
                        profile_info = None
                        print("Error scraping profile information.")
                else:
                    profile_info = None
                    print("Error scraping profile information.")
            except NoSuchElementException:
                profile_info = None
                pass  # Probably single tweet scrape, TODO: better solution
        
        if (max_items == 0):
            return None
        
        while True:
            timeline = driver.find_elements(By.CLASS_NAME, tweet_class)

            for tweet in timeline:
                try:
                    tweet_body = tweet.find_element(By.TAG_NAME, "div")
                    tweet_soup = BeautifulSoup(tweet_body.get_attribute("outerHTML"), "html.parser")
                    if is_profile:
                        tweet_data = parse_tweet(tweet_soup, existing_entries, db_collections[ATTACHMENTS_DB], is_profile, waiting_time_days, attachments, profile_info)
                    else:
                        tweet_data = parse_tweet(tweet_soup, existing_entries, db_collections[ATTACHMENTS_DB], is_profile, waiting_time_days, attachments)

                    if tweet_data == -1:
                        if not is_profile:
                            print(f"Scraped {tweet_counter} new {'tweets' if is_profile else 'comments'}.")
                            return None if len(tweets_with_replies) == 0 else tweets_with_replies  # Stop scraping
                    elif tweet_data:
                        if is_profile == False:
                            tweet_data.update({TWEET_ID_NAME: url})
                            tweet_data.update({PROFILE_TWEET_ID_NAME: profile_tweet})
                            tweet_data.update({"depth_int": depth})

                        insert_one_tweet(db_collections[db_key], tweet_data)
                        tweet_counter += 1

                        if is_profile:
                            if tweet_data["replies_int"] > 0:
                                tweets_with_replies.append(tweet_data[ID_NAME])
                        else:
                            if tweet_data["replies_int"] > 0:
                                tweets_with_replies.append(f"https://xcancel.com/{tweet_data['username_str']}/status/{tweet_data[ID_NAME]}")

                    if tweet_counter >= max_items:
                        print(f"Scraped {tweet_counter} new {'tweets' if is_profile else 'comments'}.")
                        return tweets_with_replies  # Stop if max tweets reached
                except NoSuchElementException:
                    pass  # Ignore non-tweet elements
            
            # Handle pagination
            try:
                load_more = driver.find_elements(By.LINK_TEXT, "Load more")
                no_more = driver.find_elements(By.XPATH, "//h2[contains(.,'No more items')]")
                icon_down = driver.find_elements(By.CSS_SELECTOR, "a.icon-down")

                if load_more:
                    driver.get(load_more[0].get_attribute('href'))
                    sleep(SLEEPER_MIN + SLEEP_INTERVAL())
                elif no_more or icon_down:
                    print(f"Scraped {tweet_counter} new {'tweets' if is_profile else 'comments'}.")
                    return None if len(tweets_with_replies) == 0 else tweets_with_replies
                else:
                    print("No pagination elements found.")
                    driver.save_screenshot("error.png")
                    if attempt < MAX_ATTEMPTS - 1:  # Only retry if we haven't hit max attempts
                        print(f"Retrying in 120 seconds...")
                        sleep(120 + SLEEP_INTERVAL())
                        break  # Break the inner while loop to retry the attempt
                    else:
                        print("Max attempts reached. Aborting.")
                        return None if len(tweets_with_replies) == 0 else tweets_with_replies
            except NoSuchElementException:
                print("Error finding pagination elements.")
                driver.save_screenshot("error.png")
                if attempt < MAX_ATTEMPTS - 1:  # Only retry if we haven't hit max attempts
                    print(f"Retrying in 120 seconds...")
                    sleep(120 + SLEEP_INTERVAL())
                    break  # Break the inner while loop to retry the attempt
                else:
                    print("Max attempts reached. Aborting.")
                    return None if len(tweets_with_replies) == 0 else tweets_with_replies
    
    print(f"Scraping failed after {MAX_ATTEMPTS} attempts.")
    driver.save_screenshot("error.png")
    return None if len(tweets_with_replies) == 0 else tweets_with_replies


def deep_scrape(driver: WebDriver, db_collections: Any, comments: List, force_rescrape: str, max_comments: int, attachments: bool, depth: int, profile_tweet: str) -> None:
    """Recursively scrape comments of comments up to MAX_DEPTH levels deep."""
    if depth >= MAX_DEPTH:
        return  
    
    for comment_url in comments:
        nested_comments = scrape_tweets(driver, comment_url, db_collections, force_rescrape, max_comments, False, 0, attachments, depth, profile_tweet)
        if nested_comments:
            deep_scrape(driver, db_collections, nested_comments, force_rescrape, max_comments, attachments, depth + 1, profile_tweet)


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
    help="Force rescraping: 'both' for tweets and comments, 'tweets' for tweets only, 'comments' for comments only, 'none' for no force.")
    parser.add_argument("--deep", action="store_true", help="Scrape comments of comments.")
    
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
        new_tweet = scrape_tweets(driver, tweet_url(profile_url, args.tweet), db_collections, args.force, 1, True, 0, args.attachments)
        if args.max_comments > 0:
            comments_scraped = scrape_tweets(driver, tweet_url(profile_url, args.tweet), db_collections, args.force, args.max_comments, False, 0, args.attachments, 1, tweet_url(profile_url, args.tweet))
            if comments_scraped and args.deep:
                print("Start deep scraping...")
                deep_scrape(driver, db_collections, comments_scraped, args.force, args.max_comments, args.attachments, 2, tweet_url(profile_url, args.tweet))
    else:
        new_tweets = scrape_tweets(driver, profile_url, db_collections, args.force, args.max_tweets, True, args.waiting_time, args.attachments)
        if new_tweets and args.max_comments > 0:
            for tweet_id in new_tweets:
                comments_scraped = scrape_tweets(driver, tweet_url(profile_url, tweet_id), db_collections, args.force, args.max_comments, False, args.waiting_time, args.attachments, 1, tweet_url(profile_url, tweet_id))
                if comments_scraped and args.deep:
                    print("Start deep scraping...")
                    deep_scrape(driver, db_collections, comments_scraped, args.force, args.max_comments, args.attachments, 2, tweet_url(profile_url, tweet_id))
    
    print("Scraping completed.")
    driver.quit()


if __name__ == '__main__':
    main()
