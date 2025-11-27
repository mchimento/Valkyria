#!/usr/bin/env python3
"""
Entry point for Tango Studio
"""
from app.application import TangoStudioApp

def main():
    app = TangoStudioApp()
    app.run()

if __name__ == "__main__":
    main()
