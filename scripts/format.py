#!/usr/bin/env python3
"""
Code formatting script using Black.
Usage:
    python scripts/format.py          # Check formatting
    python scripts/format.py --fix    # Apply formatting
"""

import subprocess
import sys
import os

def run_black(check_only=True):
    """Run Black code formatter."""
    
    # Change to project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    # Build command
    cmd = [sys.executable, "-m", "black", "src/", "main.py"]
    
    if check_only:
        cmd.extend(["--check", "--diff"])
        print("🔍 Checking code formatting with Black...")
    else:
        print("🔧 Applying Black formatting...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
            
        if result.returncode == 0:
            if check_only:
                print("✅ All files are properly formatted!")
            else:
                print("✅ Code formatting applied successfully!")
        else:
            if check_only:
                print("❌ Some files need formatting. Run with --fix to apply changes.")
            else:
                print("❌ Formatting failed!")
                
        return result.returncode == 0
        
    except FileNotFoundError:
        print("❌ Black is not installed. Install it with: pip install black")
        return False

if __name__ == "__main__":
    check_only = "--fix" not in sys.argv
    success = run_black(check_only=check_only)
    sys.exit(0 if success else 1)