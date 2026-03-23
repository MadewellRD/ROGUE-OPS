#
# law_parser.py
#
# Contains the deterministic rule engine for checking compliance against LAW documents.
#

def check_law_exit_conformance(indicator_data: dict, entry_price: float, current_price: float, law_exit_content: str) -> bool:
    """
    Checks if the current market conditions trigger an exit based on LAW_Exit.md.

    This is a simplified parser for the PoC.

    Args:
        indicator_data: A dictionary of the current market indicators.
        entry_price: The price at which the position was entered.
        current_price: The current real-time price of the asset.
        law_exit_content: The string content of the LAW_Exit.md file.

    Returns:
        True if an exit condition is met, False otherwise.
    """
    print("  [PROCESS] Checking position conformance against LAW_Exit.md...")

    # --- Simplified Rule Engine ---
    # Simulating rules from LAW_Exit.md:
    # Rule 1: RSI(7) momentum failure (drops below 45). This is a hard exit.
    # Rule 2: Profit target of +70% is hit.
    # Rule 3: Stop loss of -20% is hit.
    
    rsi_value = indicator_data.get("RSI(7)")
    
    # Check RSI momentum failure
    if rsi_value and rsi_value < 45:
        print(f"  [!! TRIGGER !!] LAW OF RSI FAIL-SAFE: RSI ({rsi_value}) has dropped below 45. EXIT REQUIRED.")
        return True

    # Check Profit Target / Stop Loss
    if entry_price > 0: # Avoid division by zero
        percent_change = ((current_price - entry_price) / entry_price) * 100
        
        if percent_change >= 70:
            print(f"  [!! TRIGGER !!] LAW OF PROFIT LOCK: Position is up {percent_change:.2f}%. EXIT REQUIRED.")
            return True
        
        if percent_change <= -20:
            print(f"  [!! TRIGGER !!] LAW OF RISK SUPREMACY: Position is down {percent_change:.2f}%. EXIT REQUIRED.")
            return True

    print("  [OK] No exit conditions met. Position remains open.")
    return False


def check_law_entry_conformance(indicator_data: dict, law_entry_content: str) -> bool:
    """
    Checks if the current market indicators conform to the LAW_Entry doctrine.
    """
    print("  [PROCESS] Checking indicator conformance against LAW_Entry.md...")
    
    rsi_value = indicator_data.get("RSI(7)")
    vwap_status = indicator_data.get("Price vs VWAP", "")

    rule_rsi_met = (rsi_value or 0) > 55
    print(f"    - Rule Check: RSI > 55. Current: {rsi_value}. Met: {rule_rsi_met}")

    rule_vwap_met = vwap_status in ["reclaiming from below", "well above"]
    print(f"    - Rule Check: VWAP status is 'reclaiming' or 'well above'. Current: '{vwap_status}'. Met: {rule_vwap_met}")

    is_compliant = rule_rsi_met and rule_vwap_met

    if is_compliant:
        print("  [OK] All entry LAWs are satisfied.")
    else:
        print("  [FAIL] Entry conditions do not conform to LAW.")
        
    return is_compliant
