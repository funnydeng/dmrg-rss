#!/usr/bin/env python3
"""
Legacy wrapper for DMRG RSS generation.
This file maintains backward compatibility by importing and running the new modular application.
"""

# Import the new modular application
from src.main import main

if __name__ == "__main__":
    # Run the main application
    main()
