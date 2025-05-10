#!/bin/bash
# ~/Arkkeys/pi/scripts/startup.sh

# 1) Activate the virtualenv
source /home/arktype-pi/Arkkeys/.venv/bin/activate

# 2) Change to project directory (optional, but good practice)
cd /home/arktype-pi/Arkkeys

# 3) Run your desired Python command. For demo:
python pi/display/segment_test.py

# Or to start your Bottle API:
# python pi/api/app.py
