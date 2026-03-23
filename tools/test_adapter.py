#
# test_adapter.py - FINAL VERSION
#

import logging
import random

# Imports will now work because we are running from the correct directory.
from rogue_ops.brokerage.ibkr_connection import IBKRConnection
from rogue_ops.brokerage.execution_client import ExecutionClient
from rogue_ops.brokerage.ibkr_adapter import IBKRPaperAdapter
from rogue_ops.brokerage.app import IBKRBrokerAdapterContract

# --- TEST CONFIGURATION ---
HOST = "10.138.0.6"
PORT = 7497
CLIENT_ID = random.randint(200, 999)
ACCOUNT_ID = "DU1234567"

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')

def run_adapter_test():
    """
    Initializes the brokerage stack and tests the adapter's execute method.
    """
    print("\n--- Starting IBKR Adapter Unit Test ---")
    ibkr_conn = None
    try:
        print("[TEST] Initializing master IBKR connection...")
        ibkr_conn = IBKRConnection(HOST, PORT, CLIENT_ID)
        ibkr_conn.connect_and_start()
        
        exec_client = ExecutionClient(ibkr_conn)
        adapter = IBKRPaperAdapter(exec_client)
        print("[TEST] Brokerage stack is live and adapter is ready.")

        intent = {
            "intent_id": f"adapter_test_{random.randint(1000,9999)}",
            "symbol": "SPY",
            "direction": "LONG",
            "quantity": 1,
            "order_type": "MKT"
        }
        print(f"\n[TEST] Created sample intent: {intent}")

        print("[TEST] Validating intent...")
        validation_result = adapter.validate_intent(intent)
        if not validation_result["valid"]:
            raise Exception(f"Intent validation failed: {validation_result.get('reason')}")
        
        print("[TEST] Validation passed. Executing intent...")
        execution_result = adapter.execute(intent)

        if execution_result.get("status") == "SUBMITTED_TO_BROKER":
            print("\n[SUCCESS] Adapter successfully submitted order to broker.")
        else:
            raise Exception(f"Execution failed with status: {execution_result}")

    except Exception as e:
        print(f"\n[FAILURE] Adapter test failed critically: {e}")
    finally:
        if ibkr_conn and ibkr_conn.is_connected():
            print("\n[TEST] Shutting down IBKR connection.")
            ibkr_conn.shutdown()
        print("--- Adapter Unit Test Complete ---")

if __name__ == "__main__":
    run_adapter_test()
