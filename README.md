Host Machine (macOS)
Open Terminal

Go to the host folder

bash
Copy
Edit
cd ~/ARKeys/host
Activate your virtual environment

bash
Copy
Edit
source .venv/bin/activate
(First‐time only) Install Python dependencies

bash
Copy
Edit
pip install --upgrade -r requirements.txt
Grant Accessibility permission

Open System Preferences → Security & Privacy → Privacy → Accessibility

Click “+” and add your Terminal app (so the keystroke listener can run).

Start the WebSocket metrics server

bash
Copy
Edit
python api/host_ws.py
You should see:

nginx
Copy
Edit
Starting WebSocket metrics server on port 8765…
(Optional) Run the on-screen overlay
In a second Terminal tab (with the same venv active):

bash
Copy
Edit
python listener/listener_overlay.py
Press Ctrl+O to toggle it on/off.

Leave these processes running whenever you want live WPM/accuracy reporting.

Raspberry Pi (2.13″ E-Ink Display)
SSH into the Pi (or open a terminal on the device)

Go to the display folder

bash
Copy
Edit
cd ~/ARKeys/pi/display
Activate your virtual environment

bash
Copy
Edit
source ~/.venv/bin/activate
(First‐time only) Install Python dependencies

bash
Copy
Edit
pip install --upgrade -r requirements.txt
Enable SPI interface

bash
Copy
Edit
sudo raspi-config
Select Interface Options → SPI → Enable

Run the home-screen renderer

bash
Copy
Edit
python home_screen.py
It will connect to your host’s WebSocket, show a clock when idle, and live WPM/ACC when you type.

Things to do for future
Automate on Boot
Host (macOS) with launchd
Create ~/Library/LaunchAgents/com.arkeys.hostws.plist containing your ExecStart command to run host_ws.py in the venv.

Load it:

bash
Copy
Edit
launchctl load ~/Library/LaunchAgents/com.arkeys.hostws.plist
Raspberry Pi with systemd
Create /etc/systemd/system/arkeys-display.service:

ini
Copy
Edit
[Unit]
Description=ARKeys E-Ink Display Service
After=network.target

[Service]
User=pi
ExecStart=/home/pi/.venv/bin/python /home/pi/ARKeys/pi/display/home_screen.py
Restart=always

[Install]
WantedBy=multi-user.target
Enable & start it:

bash
Copy
Edit
sudo systemctl enable arkeys-display
sudo systemctl start arkeys-display
