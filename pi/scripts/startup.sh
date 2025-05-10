#!/bin/bash
# Activate the right venv
source /home/arktype-pi/ARKeys/.venv/bin/activate

# Go to the display folder where segment_test.py lives
cd /home/arktype-pi/ARKeys/pi/display

# Run the demo
python3 segment_test.py
