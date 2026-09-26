"""Permite ejecutar el comprobador con `python -m pysion.check`."""

import sys

from pysion.check.cli import main

if __name__ == "__main__":
    sys.exit(main())
