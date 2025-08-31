#!/usr/bin/env python3
"""
Simple test runner for the FastAPI app tests.
Run this script to execute all tests or specific test classes.
"""

import sys
import os

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    import pytest
    
    # Run all tests
    print("Running FastAPI app tests...")
    exit_code = pytest.main([
        "test_files.py",
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "-s"  # Show print statements
    ])
    
    sys.exit(exit_code)
