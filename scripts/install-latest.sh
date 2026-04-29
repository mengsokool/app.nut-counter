#!/usr/bin/env sh
set -eu

echo "Fetching latest release from GitHub..."
DOWNLOAD_URL=$(curl -sL https://api.github.com/repos/mengsokool/app.nut-counter/releases/latest | grep "browser_download_url.*deb" | cut -d '"' -f 4)

if [ -z "$DOWNLOAD_URL" ]; then
    echo "Error: Could not find latest release deb package."
    exit 1
fi

# Download to /tmp to avoid permission issues with _apt user
TEMP_DEB="/tmp/nut-counter-latest.deb"
echo "Downloading $DOWNLOAD_URL to $TEMP_DEB..."
wget -qO "$TEMP_DEB" "$DOWNLOAD_URL"

echo "Installing..."
sudo apt install -y "$TEMP_DEB"

# Clean up
rm -f "$TEMP_DEB"
echo "Installation complete!"
