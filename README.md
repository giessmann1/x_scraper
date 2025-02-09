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

| Parameter         | Short | Required | Default | Description |
|------------------|-------|----------|---------|-------------|
| `--profile`      | `-p`  | Yes      | N/A     | The username of the profile to scrape. Can be provided with or without `@`. |
| `--tweet`        | `-t`  | No       | N/A     | The status id of a single tweet from a user to scrape. |
| `--max-comments` | N/A   | No       | `10`    | The maximum number of comments to scrape per tweet. |
| `--attachments`  | N/A   | No       | `yes`   | Whether to download tweet attachments as binary files. Possible values: `yes` or `no`. |
| `--waiting-time` | N/A   | No       | `7`     | Time period (in days) to wait before scraping a new tweet. This provides people enough time to reply. |
| `--force`        | `-f`  | No       | N/A     | Force all tweets and comments to be rescraped. |
| `--deep`         | N/A   | No       | N/A     | Scrape comments of comments. |

### Example Commands
Scrape tweets from a user profile without downloading attachments:

```sh
python3 scraper.py -p @elonmusk --attachments no
```

Scrape tweets while allowing up to 100 comments per tweet:

```sh
python3 scraper.py -p @elonmusk --max-comments 100
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