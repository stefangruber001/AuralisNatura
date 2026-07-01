#!/usr/bin/env python3
"""Entry point: python run.py  (or use the start_auralis launcher)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server.app import main
if __name__ == "__main__":
    main()
