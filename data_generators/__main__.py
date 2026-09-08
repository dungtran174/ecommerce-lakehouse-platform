"""Package execution entrypoint for data_generators module.

Allows invoking the suite via:
python -m data_generators --scale small --target all
"""

import sys

from data_generators.cli import main

if __name__ == "__main__":
    main(sys.argv[1:])
