#!/usr/bin/env python3
"""
Entry point for Tango Studio
"""
from app.application import TangoStudioApp
from app.logging_config import setup_logging

def main():
    setup_logging()
    app = TangoStudioApp()
    app.run()

if __name__ == "__main__":
    main()
