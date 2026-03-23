def classify_ibkr_error(code: int) -> str:
    if 2100 <= code <= 2199:
        return "STATUS"
    if code == 200:
        return "CONTRACT_ERROR"
    if code in (201, 10147):
        return "ORDER_REJECTED"
    if code == 1100:
        return "DISCONNECTED"
    if code == 1101:
        return "RECONNECTED"
    return "UNKNOWN"
