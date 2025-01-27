#!/bin/bash

# Add this to your crontab 0 23 * * 0 /bin/bash $HOME/x_scraper/scraper-starter.sh

cd $HOME/x_scraper
filename=scraper-log.txt
if [ ! -f $filename ]
then
    touch $filename
fi

# If you use Python Virtual Environment
source .env/bin/activate
echo $(date +'%Y-%m-%d') >> $filename
python3 scraper.py -p @elonmusk -t 1881547272556777647 >> $filename
deactivate