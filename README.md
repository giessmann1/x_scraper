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
python scraper.py -p <username> [options]
```

For automated start with crontab, see scraper-starter.sh

### Parameters

| Parameter         | Short | Required | Default | Description |
|------------------|-------|----------|---------|-------------|
| `--profile`      | `-p`  | Yes      | N/A     | The username of the profile to scrape. Can be provided with or without `@`. |
| `--max-comments` | N/A   | No       | `10`    | The maximum number of comments to scrape per tweet. |
| `--attachments`  | N/A   | No       | `yes`   | Whether to download tweet attachments as binary files. Possible values: `yes` or `no`. |
| `--waiting-time` | N/A   | No       | `7`     | Time period (in days) to wait before scraping a new tweet. This provides people enough time to reply. |

### Example Commands
Scrape tweets from a user profile without downloading attachments:

```sh
python scraper.py -p @elonmusk --attachments no
```

Scrape tweets while allowing up to 20 comments per tweet:

```sh
python scraper.py -p @elonmusk --max-comments 20
```

## Notes
- Be careful with the scraping of large amounts of data, as this can be very heavy on the Nitter service in use here.
- Scraping may violate X's terms of service (which you technically do not agree to).

## License
This project is licensed under the MIT License.

## Contributions
Pull requests and suggestions are welcome! Feel free to submit issues or feature requests. Please note that I am not a professional software developer, just a researcher trying to getting his data.