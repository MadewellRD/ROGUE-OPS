#!/usr/bin/env python3

import sys
import os
import json

print("--- FINAL ROGUE:OPS Environment Diagnostic ---")
print(f"Current Working Directory: {os.getcwd()}")

# --- STEP 1: Report the PYTHONPATH environment variable ---
python_path_env = os.environ.get('PYTHONPATH')
print(f"\nValue of PYTHONPATH environment variable: {python_path_env}")

# --- STEP 2: Report the final, effective sys.path ---
print("\n--- Final Python Search Path (sys.path) ---")
print(json.dumps(sys.path, indent=2))

# --- STEP 3: Manually check for the existence of the target path ---
target_path = "/opt/rogue/rogue-core/rogue_ops"
print(f"\n--- Checking for Target Path ---")
print(f"Checking if path exists: {target_path}")
path_exists = os.path.isdir(target_path)
print(f"Does path exist? {path_exists}")

if path_exists:
    print(f"Checking for __init__.py in: {target_path}")
    init_exists = os.path.isfile(os.path.join(target_path, "__init__.py"))
    print(f"Does __init__.py exist? {init_exists}")

print("\n--- Diagnostic Complete ---")
