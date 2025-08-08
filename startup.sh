#!/bin/sh

# Create X11 directory with proper permissions
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# Remove any existing X lock files
rm -f /tmp/.X0-lock

echo "Starting Xvfb..."
# Run Xvfb on display 0 with better screen configuration (1920x1080 for full HD)
Xvfb :0 -screen 0 1920x1080x24 -ac &
XVFB_PID=$!

# Wait for Xvfb to start
sleep 3

echo "Starting fluxbox..."
# Run fluxbox window manager on display 0
DISPLAY=:0 fluxbox &
FLUXBOX_PID=$!

# Wait for fluxbox to start
sleep 2

echo "Starting x11vnc..."
# Run x11vnc on display 0 for remote access (with password authentication)
DISPLAY=:0 x11vnc -display :0 -forever -shared -passwd 1234 &
VNC_PID=$!

# Wait for x11vnc to start
sleep 2

echo "VNC server started on display :0"
echo "Connect with: vnc://localhost:5900 (password: 1234)"

# Keep container running with tail
tail -f /dev/null
