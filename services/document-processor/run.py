#!/usr/bin/env python3
"""OCR Agent - Simple Startup"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    # Ensure we're in the right directory
    os.chdir(Path(__file__).parent / "app")

    print("Starting OCR Agent...")
    print("Docs: http://localhost:8001/docs")
    print("=" * 40)

    # Start the server
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n✋ Server stopped")

if __name__ == "__main__":
    main()