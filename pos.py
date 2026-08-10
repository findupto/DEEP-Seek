"""Canonical POS entry point.

The previous legacy implementation contained a syntax error and several incompatible
monkey patches. The application now has one canonical launcher so every entry point
opens the same POS UI.
"""
from modern_ui import main

if __name__ == '__main__':
    main()
