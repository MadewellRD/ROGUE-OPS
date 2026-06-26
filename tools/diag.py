#!/usr/bin/env python3

import sys
import os
import json

print("--- ROGUE:OPS Import Diagnostic ---")
print(f"Executing as user: {os.geteuid()}")
print(f"Current Working Directory: {os.getcwd()}")

# --- STEP 1: Add the project path ---
CORE_PROJECT_PATH = "/opt/rogue/rogue-core"
if CORE_PROJECT_PATH not in sys.path:
    sys.path.insert(0, CORE_PROJECT_PATH)
    print(f"[ACTION] Injected path: {CORE_PROJECT_PATH}")
else:
    print(f"[INFO] Path already exists: {CORE_PROJECT_PATH}")

print("\n--- CURRENT PYTHON SEARCH PATH (sys.path) ---")
print(json.dumps(sys.path, indent=2))

# --- STEP 2: Check filesystem access from within Python ---
print("\n--- CHECKING DIRECTORY PERMISSIONS ---")
try:
    print(f"Attempting to list contents of: {CORE_PROJECT_PATH}")
    core_contents = os.listdir(CORE_PROJECT_PATH)
    print("[SUCCESS] Can read /opt/rogue/rogue-core/")
    
    if "rogue_ops" in core_contents:
        print("    - 'rogue_ops' directory found.")
        
        rogue_ops_path = os.path.join(CORE_PROJECT_PATH, "rogue_ops")
        print(f"Attempting to list contents of: {rogue_ops_path}")
        rogue_ops_contents = os.listdir(rogue_ops_path)
        print("[SUCCESS] Can read /opt/rogue/rogue-core/rogue_ops/")
        
        if "__init__.py" in rogue_ops_contents:
            print("    - '__init__.py' file FOUND in 'rogue_ops'. This is a valid package.")
        else:
            print("    - [CRITICAL FAILURE] '__init__.py' file NOT FOUND in 'rogue_ops'. This is NOT a package.")

    else:
        print("    - [CRITICAL FAILURE] 'rogue_ops' directory NOT FOUND in /opt/rogue/rogue-core/")

except OSError as e:
    print(f"[CRITICAL FAILURE] Cannot read project directories. OS Error: {e}")
except Exception as e:
    print(f"[CRITICAL FAILURE] An unexpected error occurred during directory check: {e}")

# --- STEP 3: Attempt the import ---
print("\n--- ATTEMPTING THE IMPORT ---")
try:
    print("Executing: from rogue_ops.brokerage.ibkr_connection import IBKRConnection")
    from rogue_ops.brokerage.ibkr_connection import IBKRConnection
    print("\n[SUCCESS] The import was successful.")
    print("The problem is not the import itself, but the context in which the other scripts are run.")
except ImportError as e:
    print(f"\n[FINAL DIAGNOSIS] The import failed with an ImportError.")
    print(f"Error details: {e}")
except ModuleNotFoundError as e:
    print(f"\n[FINAL DIAGNOSIS] The import failed with a ModuleNotFoundError.")
    print(f"Error details: {e}")
except Exception as e:
    print(f"\n[FINAL DIAGNOSIS] The import failed with an unexpected exception.")
    print(f"Error details: {e}")

print("\n--- Diagnostic Complete ---")
