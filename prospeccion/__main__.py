"""Punto de entrada:  python3 -m prospeccion dominios.txt --out informes/"""

import sys

from .cli import main

sys.exit(main())
