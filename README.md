# sdm630-py

Python script to read power meter data from sdm630 meters and publish them via mqtt and/or into a sqlite database.

I'm using this script on a Raspberry Pi 4 with rasbian buster with an RS485 usb adapter.

## Requirements

- You need an RS485 usb adapter
- Python3 is required (developed with 3.10.12)
- If you want to use the sqlite export, it is a little bit more complex, because the compiled python3 packages from apt-get have no sqlite support and you have to compile python on our own (see below)

## Installation

### Install python3

With sqlite support

- run `compile_python_sqlite.sh` to compile python with sqlite support (takes long time!)

Without sqlite support

- `sudo apt-get install python3`

### Setup python3

Setup a virtual environment

- I recommend to create and use a virtual python environment for this script
- Open the sdm630-py path
- `python3.10.12 -m venv py-env` to create a virtual env
- `source py-env/bin/activate` to use virtual env
- `pip3 install -r requirements.txt` to install python modules

Setup without virtual environment

- `pip3 install -r requirements.txt` to install python modules

### Edit Config

- Edit `config.py`, set your device path ("dev"), mqtt settings, sqlite path... 
- Possible loglevels are: ERROR, DEBUG (others are currently not in use). Set loglevel to "DEBUG" for testing

## First run

- Set the loglevel in config.py to "DEBUG" and run `./sdm630-py.sh`
- You should see a lot debug informations, but no Exceptions
- Check if the sqlite database has been created in the specified path (config.py)
- Check if the mqtt messages will be published correctly
- Exit with CTRL+C

## Install systemd service and enable autostart

- Remind to set loglevel back to "ERROR" (in config.py) to avoid huge log files
- Set the correct path for sdm630-py.sh in `sdm630-py.service`
- `sudo cp sdm630-py.service /etc/systemd/system` to copy the service to your systemd path
- `sudo systemctl enable sdm630-py` to start sdm630-py automatically
- `sudo systemctl start sdm630-py` to start sdm630-py now
- `sudo systemctl status sdm630-py` to check if there are erorrs (1 error "reading failed" at the begining is ok)

## Misc

For bugs or feature requests, please create an issue on github. "Star" or "Watch" the github repo if you like my work.

Regards, Arne Drees