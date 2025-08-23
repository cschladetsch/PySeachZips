#!/usr/bin/env python3

from google_takeout_scanner import GoogleTakeoutScanner

# Test drive detection
scanner = GoogleTakeoutScanner()
drives = scanner.get_available_drives()
print(f"Detected {len(drives)} drives:")
for drive in drives:
    print(f"  - {drive}")

# Test WSL detection
is_wsl = scanner.is_wsl()
print(f"\nRunning in WSL: {is_wsl}")

scanner.close()