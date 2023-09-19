### Group Members:
1. Aayush Jain
2. Kunjan Shah

### Getting Started

1. Create a virtual environment with `python -m venv ./venv` (Use Python 3.9+)
2. Activate virtual environment with `source ./venv/bin/activate`
3. Install dependencies with `pip install -r requirements-dev.txt`
4. Run `python game.py -h` for expected CLI arguments to play the game

### Code Styling

To ensure uniform styling, the following tools have been set up:
- `black` - Ensures standard code formatting, run `black game.py`
- `flake8` - Verifies common issues in Python code, run `flake8 game.py`
- `reorder-python-imports` - Reorders Python imports in separate lines to ensure that no merge conflicts arise due to 
imports, run `reorder-python-imports game.py` 
