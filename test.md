### 1. Update the setup script to preserve data
Right now, `setup_profile.sh` deletes `/tmp/webtactix_chrome_profile` every time it runs. To make your logins persistent, simply remove the `--delete` flag from the `rsync` command inside `setup_profile.sh` (line 14).

### 2. Pre-authenticate the Automation Profile manually
Before running the agent script, you can manually open Chrome using that specific temporary profile and log into whatever accounts the agent will need:
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --user-data-dir="/tmp/webtactix_chrome_profile"
```
When this browser window opens, log into Google, solve any CAPTCHAs, and then close the window completely. 

### 3. Run the Agent
Once the profile is primed, you can run the agent script as normal:
```bash
source .venv/bin/activate && export PYTHONPATH=. 
python3 run_real_world.py --url "https://www.facebook.com/" --intent "List all of my friends" --network-idle-timeout 1000 --layout-stable-timeout 1000
```
Because the profile wasn't wiped by the setup script, Playwright will load it up and inherit all the active logins you just performed!