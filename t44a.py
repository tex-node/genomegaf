#!/usr/bin/env python3
"""Thin entry point -- see research/t44a/cli.py for the real logic.

    python t44a.py records.txt
    python t44a.py ./exports/
    python t44a.py dow.txt wti.txt ndx.txt
    cat records.txt | python t44a.py -
"""

from research.t44a.cli import main

if __name__ == "__main__":
    main()
