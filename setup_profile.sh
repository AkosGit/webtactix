#!/bin/bash
# setup_profile.sh
# This script clones the active user's Google Chrome Default profile and Local State
# into a temporary directory. This is necessary because Chrome 136+ actively blocks 
# remote-debugging (Playwright/Selenium) on the primary user-data-dir for security.

echo "Cloning Chrome profile to bypass macOS remote debugging security restrictions..."

# Kill any existing Chrome instances using the cloned profile
pkill -9 -f webtactix_chrome_profile

SRC_DEFAULT="$HOME/Library/Application Support/Google/Chrome/Default"
SRC_LOCAL_STATE="$HOME/Library/Application Support/Google/Chrome/Local State"
DST="/tmp/webtactix_chrome_profile"

mkdir -p "$DST"

# Rsync the Default profile directory and Local State file
rsync -a --delete "$SRC_DEFAULT" "$DST/"
rsync -a "$SRC_LOCAL_STATE" "$DST/"

echo "Chrome profile successfully cloned to $DST."
