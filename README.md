# X Scraper (2025)

## Overview
X Scraper is a command-line tool for scraping tweets and comments from a specified profile on X (formerly Twitter) without registration needed. It features advanced bot detection evasion, Cloudflare bypass capabilities, and visual debugging through VNC. The tool allows customization of scraping behavior, including the number of comments, whether to download attachments, and a waiting time before fetching new tweets.

❗ This is an actively maintained repository for scholarly purposes only. If you have suggestions for further improvement or find bugs: [Email me](mailto:nico.giessmann@uni-luebeck.de)

## 🚀 Quick Start

**New to the project?** Check out [QUICK_START.md](QUICK_START.md) for a simple guide to get started in 2 minutes!

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

## Running Options

The scraper can be run in two different ways:

### Option 1: Local Setup (Traditional)
**Prerequisites:**
- Python 3.11+
- MongoDB installed and running
- Chrome browser and Chromedriver installed
- All Python dependencies installed

**Setup:**
```bash
# Create Python virtual environment
python3 -m venv .env
source .env/bin/activate
pip3 install -r requirements.txt

# Create .secrets/ directory with MongoDB credentials
mkdir .secrets/
echo -n "admin" > .secrets/mongodb_user.txt
echo -n "password" > .secrets/mongodb_pwd.txt
echo -n "localhost" > .secrets/host.txt

# Start MongoDB (if using Docker for database)
sh startdb.sh
```

**Usage:**
```bash
python3 scraper.py -p @elonmusk --max-tweets 10
```

### Option 2: Full Docker (Zero Setup)
**Prerequisites:**
- Docker and Docker Compose installed
- Nothing else needed!

**Usage:**
```bash
# Make scripts executable
chmod +x run-scraper-full-docker.sh start-services.sh stop-services.sh run-scrape.sh

# Start services (runs once, keeps containers active)
./start-services.sh

# Run scraping jobs (executes inside running container)
./run-scrape.sh -p @elonmusk --max-tweets 10

# Or use the all-in-one script (starts services if needed)
./run-scraper-full-docker.sh -p @elonmusk --max-tweets 10
```

## Docker Usage (Advanced)

For users who want more control over their Docker setup, there are additional Docker options available.

### Quick Start with Docker (Advanced Setup)

For users who want to use Docker with custom MongoDB credentials:

1. **Setup secrets**:
```bash
mkdir -p .secrets
echo -n "admin" > .secrets/mongodb_user.txt
echo -n "password" > .secrets/mongodb_pwd.txt
```

2. **Run the scraper in Docker**:
```bash
# Make the script executable
chmod +x run-scraper-docker.sh

# Run with arguments (same as local usage)
./run-scraper-docker.sh -p @elonmusk --max-tweets 50 --max-comments 10
```

### Manual Docker Commands

If you prefer to run Docker commands directly:

**Start Services (Persistent):**
```bash
# Start all services and keep them running
docker compose up -d

# Run scraping jobs inside the running container
docker compose exec scraper python scraper.py -p @elonmusk --max-tweets 10

# Stop all services
docker compose down
```

**Custom Credentials:**
```bash
# Set custom credentials as environment variables
export MONGO_USER=myuser
export MONGO_PASSWORD=mypassword

# Start all services and keep them running
docker compose up -d

# Run scraping jobs inside the running container
docker compose exec scraper python scraper.py -p @elonmusk --max-tweets 10

# Stop all services
docker compose down
```

### Hybrid Approach: Docker Database + Local Scraper

You can also run just the database in Docker while running the scraper locally:

```bash
# Start only the database in Docker (Advanced setup)
chmod +x startdb-docker.sh
./startdb-docker.sh

# Run the scraper locally (make sure to update .secrets/host.txt to "localhost")
python scraper.py -p @elonmusk --max-tweets 10
```

**Or use Docker for database only:**
```bash
# Start only the database
docker compose up -d db

# Run the scraper locally (connect to localhost:27017)
python scraper.py -p @elonmusk --max-tweets 10
```

### Docker Configuration

| Feature | Local Setup | Docker Setup |
|---------|-------------|--------------|
| **Prerequisites** | Python, MongoDB, Chrome, Chromedriver | Docker + Docker Compose |
| **Setup Required** | Manual installation | None (or set env vars for custom credentials) |
| **MongoDB** | Local installation | Included in container |
| **Chrome/Chromedriver** | Local installation | Included in container |
| **Credentials** | .secrets files | Default (admin/password) or environment variables |
| **Customization** | Full control | Full control via environment variables |
| **Ease of Use** | Complex | Very Easy |

**Docker includes:**
- **Scraper container**: Python environment with Chromium and Chromedriver
- **Database container**: MongoDB with persistent storage
- **Network**: Isolated network for secure communication
- **Credentials**: Default admin/password or custom via environment variables
- **Volumes**: Persistent data storage and output directory
- **VNC Server**: Visual debugging with remote desktop access
- **Advanced Bot Evasion**: Cloudflare bypass and anti-detection techniques

### VNC Visual Debugging

The Docker setup includes a VNC server for visual debugging and monitoring:

**Connect to VNC:**
```bash
# Connect using any VNC client
vnc://localhost:5900

# Or use macOS Screen Sharing
open vnc://localhost:5900
```

**VNC Details:**
- **URL**: `vnc://localhost:5900`
- **Password**: `1234`
- **Resolution**: 1920x1080 (Full HD)
- **Features**: Watch Chrome browser in real-time, debug bot detection, observe Cloudflare bypass

**What you can see:**
- Real-time browser navigation
- Cloudflare bypass process (blank page → link click → verification)
- Anti-bot verification pages
- Scraping progress and pagination
- Screenshots and debugging information

### Output and Data

- **Database data**: Stored in `./xdb-data/` directory
- **Scraper output**: Available in `./scraper-output/` directory
- **Logs**: Available through Docker logs
- **Screenshots**: Debug images saved to container (accessible via VNC)

### Troubleshooting Docker

If you encounter issues:

1. **Check container logs**:
```bash
docker compose logs scraper
```

2. **Rebuild the container**:
```bash
docker compose build --no-cache scraper
```

3. **Clean up and restart**:
```bash
docker compose down -v
docker compose up -d
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
| `-p`  | `--profile`      | `str`  | —        | yes      | Profile username to scrape.                                |
| `-t`  | `--tweet`        | `str`  | `None`   | no       | ID of a single tweet to scrape.                            |
|       | `--max-comments` | `int`  | `10`     | no       | Maximum number of comments per tweet.                      |
|       | `--max-tweets`   | `int`  | `10`     | no       | Maximum number of tweets in profile to scrape.             |
|       | `--attachments`  | `bool` | `"yes"`  | no       | Scrape attachments (`yes` or `no`).                        |
|       | `--waiting-time` | `int`  | `7`      | no       | Time (in days) to wait before scraping new tweets (ignored for comments). |
| `-f`  | `--force`        | `str`  | `"none"` | no       | Force rescraping: `both`, `tweets`, `comments`, or `none`. |
|       | `--deep`         | -      | -        | no       | Scrape comments of comments.                               |

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
- Be careful with the scraping of large amounts of data, as this can be very heavy on the Nitter service in use.
- Scraping may violate X's terms of service (which you technically do not agreed to). Check legislation in your country.

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