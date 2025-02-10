# X Scraper (2025)

## Overview
X Scraper is a command-line tool for scraping tweets and comments from a specified profile on X (formerly Twitter) without registration needed. It allows customization of scraping behavior, including the number of comments, whether to download attachments, and a waiting time before fetching new tweets.

❗ This is an actively maintained repository for scholarly purposes only. If you have suggestions for further improvement or find bugs: [Email me](mailto:nico.giessmann@uni-luebeck.de)

## Installation

Create Python virtual environment:
```bash
python3 -m venv .env
source .env/bin/activate
pip3 install -r requirements.txt
```

Create essential files:
```bash
# Create .secrets/ directory
mkdir .secrets/

# Create mongodb_user.txt and mongodb_pwd.txt and set your own username and password (no update in Python scripts necessary). Be aware of newlines, which need to be removed!

echo -n "admin" > .secrets/mongodb_user.txt
echo -n "password" > .secrets/mongodb_pwd.txt
echo -n "localhost" > .secrets/host.txt
```

Docker installation needed, see: https://docs.docker.com/engine/install/.

Starting the db:
```bash
sh startdb.sh
```

## Usage
Run the script using the following command:

```sh
python3 scraper.py -p <username> [options]
```

For automated start with crontab, see scraper-starter.sh

### Parameters

| Short | Long             | Type   | Default  | Required | Description                                                |
|-------|------------------|--------|----------|----------|------------------------------------------------------------|
| `-p`  | `--profile`      | `str`  | —        | ✅       | Profile username to scrape.                                |
| `-t`  | `--tweet`        | `str`  | `None`   | ❌       | ID of a single tweet to scrape.                            |
|       | `--max-comments` | `int`  | `10`     | ❌       | Maximum number of comments per tweet.                      |
|       | `--max-tweets`   | `int`  | `10`     | ❌       | Maximum number of tweets in profile to scrape.             |
|       | `--attachments`  | `bool` | `"yes"`  | ❌       | Scrape attachments (`yes` or `no`).                        |
|       | `--waiting-time` | `int`  | `7`      | ❌       | Time (in days) to wait before scraping new tweets (ignored for comments). |
| `-f`  | `--force`        | `str`  | `"none"` | ❌       | Force rescraping: `both`, `tweets`, `comments`, or `none`. |

### Example Commands
Scrape tweets from a user profile without downloading attachments:

```sh
python3 scraper.py -p @elonmusk --attachments no
```

Scrape tweets while allowing up to 100 tweets and 20 comments per tweet:

```sh
python3 scraper.py -p @elonmusk --max-tweets 100 --max-comments 20
```

Scrape single tweet:

```sh
python3 scraper.py -p @elonmusk -t 1881547272556777647
```

## Notes
- Be careful with the scraping of large amounts of data, as this can be very heavy on the Nitter service in use here.
- Scraping may violate X's terms of service (which you technically do not agreed to).

### Running headless on MacOS
For me, the undetected chromedriver package did not work in headless-mode with newer version of Google Chrome. Consider downgrading to [version 112](https://google-chrome.en.uptodown.com/mac/download/99265871).

You probably also need to disable Google Chrome auto-updates, which is quite hacky (credit to [Dharmesh Mansata](https://stackoverflow.com/a/64923744)):

```sh
sudo rm -rf ~/Library/Google/GoogleSoftwareUpdate/

cd /Library/Google/
sudo chown nobody:nogroup GoogleSoftwareUpdate
sudo chmod 000 GoogleSoftwareUpdate

cd ~/Library/Google/
sudo chown nobody:nogroup GoogleSoftwareUpdate
sudo chmod 000 GoogleSoftwareUpdate

cd /Library/
sudo chown nobody:nogroup Google
sudo chmod 000 Google
cd ~/Library/                                                                                                                    
sudo chown nobody:nogroup Google
sudo chmod 000 Google
```

## License
This project is licensed under the MIT License.

## Contributions
Pull requests and suggestions are welcome! Feel free to submit issues or feature requests. Please note that I am not a professional software developer, just a researcher trying to get his data.