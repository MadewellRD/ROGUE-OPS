import asyncio
import json
import hmac
import hashlib
import time
from uuid import uuid4
import websockets

# =============================
# CONFIG
# =============================

HOST = "0.0.0.0"
PORT = 8765

# This must match ROGUE later
SHARED_SECRET = b"CHANGE_ME_TO_REAL_SECRET"

# Safety
NONCE_WINDOW_SECONDS = 5

# =============================
# STATE
# =============================

seen_nonces = set()
halted = False


# =============================
# HELPERS
# =============================

def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sign_message(message: dict) -> str:
    raw = json.dumps(message, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(SHARED_SECRET, raw, hashlib.sha256).hexdigest()


def verify_message(message: dict) -> bool:
    signature = message.get("signature")
    if not signature:
        return False

    msg_copy = dict(message)
    msg_copy.pop("signature", None)

    raw = json.dumps(msg_copy, sort_keys=True, separators=(",", ":")).encode()
    expected = hmac.new(SHARED_SECRET, raw, hashlib.sha256).hexdigest()

    return hmac.compare_digest(signature, expected)


def nonce_valid(nonce: str, sent_at: str) -> bool:
    try:
        sent_ts = time.strptime(sent_at, "%Y-%m-%dT%H:%M:%SZ")
        sent_epoch = time.mktime(sent_ts)
        return abs(time.time() - sent_epoch) <= NONCE_WINDOW_SECONDS
    except Exception:
        return False


# =============================
# CORE SERVER
# =============================

async def handle_connection(ws):
    global halted

    print("[VM] ROGUE connected")

    async for raw in ws:
        try:
            msg = json.loads(raw)
        except Exception:
            print("[VM] Invalid JSON")
            continue

        if not verify_message(msg):
            print("[VM] INVALID SIGNATURE — HALTING")
            halted = True
            continue

        if not nonce_valid(msg["nonce"], msg["sent_at"]):
            print("[VM] Nonce/time invalid — ignored")
            continue

        if msg["nonce"] in seen_nonces:
            print("[VM] Replay detected — ignored")
            continue

        seen_nonces.add(msg["nonce"])

        msg_type = msg["type"]

        # =============================
        # KILL SWITCH
        # =============================
        if msg_type == "KILL_SWITCH":
            print("[VM] KILL SWITCH RECEIVED")
            halted = True
            # Here you would:
            # - cancel orders
            # - flatten positions
            continue

        if halted:
            print("[VM] HALTED — ignoring message")
            continue

        # =============================
        # EXECUTION ENVELOPE
        # =============================
        if msg_type == "EXECUTION_ENVELOPE":
            directive = msg["payload"]["decision"]["directive"]

            if directive not in ("ENTRY_AUTHORIZED", "EXIT_NOW"):
                print("[VM] Directive not allowed")
                continue

            print(f"[VM] EXECUTING directive: {directive}")

            # ---- PLACE WHERE IBKR EXECUTION WILL GO LATER ----

            result = {
                "type": "EXECUTION_RESULT",
                "version": "1.0",
                "payload": {
                    "envelope_id": msg["payload"]["envelope_id"],
                    "success": True,
                    "fill_price": 0.0,
                    "quantity": 0,
                    "executed_at": now_iso()
                },
                "sent_at": now_iso(),
                "nonce": str(uuid4())
            }

            result["signature"] = sign_message(result)
            await ws.send(json.dumps(result))

        else:
            print(f"[VM] Unknown message type: {msg_type}")


# =============================
# BOOT
# =============================

async def main():
    print(f"[VM] WebSocket server starting on {HOST}:{PORT}")
    async with websockets.serve(handle_connection, HOST, PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
