# Use Python 3.11 Alpine image as base (more lightweight)
FROM python:3.11-alpine

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:0

# Expose VNC port for remote debugging and API port
EXPOSE 5900
EXPOSE 8001

# Install system dependencies including full GUI environment
RUN apk update && apk upgrade && \
    apk add --no-cache --virtual .build-deps \
    alpine-sdk \
    curl \
    wget \
    unzip \
    gnupg && \
    apk add --no-cache \
    xvfb \
    x11vnc \
    fluxbox \
    xterm \
    libffi-dev \
    openssl-dev \
    zlib-dev \
    bzip2-dev \
    readline-dev \
    sqlite-dev \
    git \
    nss \
    freetype \
    freetype-dev \
    harfbuzz \
    ca-certificates \
    ttf-freefont \
    chromium \
    chromium-chromedriver && \
    apk del .build-deps

# Set up X11 VNC password for remote access
RUN mkdir -p ~/.vnc && echo "1234" | x11vnc -storepasswd stdin ~/.vnc/passwd

# Copy startup script
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

# Set up working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY scraper.py .
COPY database_wrapper.py .
COPY health_check.py .
COPY api.py .

# Create directory for secrets
RUN mkdir -p .secrets

# Create a non-root user with proper groups
RUN addgroup -g 1000 scraper && adduser -D -s /bin/sh -u 1000 -G scraper scraper \
    && mkdir -p /home/scraper/Downloads \
    && chown -R scraper:scraper /home/scraper \
    && chown -R scraper:scraper /app

# Default command - run startup script as root to set up X11, then start API and keep container running
CMD ["sh", "-c", "/startup.sh & sleep 10 && su scraper -c 'python /app/api.py'"]
