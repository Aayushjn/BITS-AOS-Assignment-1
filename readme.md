Group Members:

1. Aayush Jain (2023H1030083P)
2. Kunjan Shah (2019HS030072P)

Code is at: https://github.com/Aayushjn/BITS-AOS-Assignment-1/tree/dev

Getting Started

1. Create a virtual environment with `python -m venv ./venv` (Use Python 3.9+)
2. Activate virtual environment with `source ./venv/bin/activate`
3. Install dependencies with `pip install -r requirements-dev.txt` and `pip install -r requirements.txt`
4. Run `python game.py -h` for expected CLI arguments to play the game
5. Start M-1 soldiers using `python game.py --soldier <ip_address_of_soldier>`
6. Keep a note of ip addresses of soldiers in a file _`_config.toml_
7. When starting the commander, it expects a _config.toml_ file in the same location as the code. See below example file for expected parameters.
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
8. Start the commander using `python game.py --commander 0` 

Note that if a soldier is being run on a Windows machine (or a Linux machine with a firewall such as UFW), an
exception needs to be made in the firewall rules to allow incoming TCP connections on the specified port.