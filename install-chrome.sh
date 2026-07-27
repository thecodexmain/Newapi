#!/bin/bash

# Install Chrome for Selenium
echo "Installing Chrome..."

# Add Google Chrome repository
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list

# Update and install
apt-get update
apt-get install -y google-chrome-stable

# Check installation
google-chrome --version

echo "Chrome installation complete"
