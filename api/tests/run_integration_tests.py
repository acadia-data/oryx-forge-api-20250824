#!/usr/bin/env python3
"""
Test runner script for FileService integration tests.
This script can be used to run the integration tests manually.
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    """Run the integration tests"""
    # Get the directory containing this script
    test_dir = Path(__file__).parent
    api_dir = test_dir.parent
    
    # Change to the API directory
    os.chdir(api_dir)
    
    # Run pytest with the integration tests
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_file_service_integration.py",
        "-v",
        "--tb=short"
    ]
    
    print(f"Running integration tests from: {api_dir}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n" + "=" * 50)
        print("✅ All integration tests passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 50)
        print(f"❌ Integration tests failed with exit code: {e.returncode}")
        return e.returncode
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
