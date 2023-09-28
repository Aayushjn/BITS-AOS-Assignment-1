Group Members:

1. Aayush Jain
2. Kunjan Shah

Getting Started

1. Create a virtual environment with `python -m venv ./venv` (Use Python 3.9+)
2. Activate virtual environment with `source ./venv/bin/activate`
3. Install dependencies with `pip install -r requirements-dev.txt`
4. Run `python game.py -h` for expected CLI arguments to play the game
5. When starting the commander, it expects a _config.toml_ file in the same location as the code. See below for
   expected parameters.
   ```toml
   N = 8 # size of the board
   M = 5 # number of soldiers
   t = 3 # time between each missile (seconds)
   T = 18 # game time (seconds)
   soldiers = [ # addresses of each soldier (length should be at least M)
       "127.0.0.1:50051",
       "127.0.0.1:50052",
       "127.0.0.1:50053",
       "127.0.0.1:50054",
       "127.0.0.1:50055",
   ]
   ```

Note that if a soldier is being run on a Windows machine (or a Linux machine with a firewall such as UFW), an
exception needs to be made in the firewall rules to allow incoming TCP connections on the specified port.