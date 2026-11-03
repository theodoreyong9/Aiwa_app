"""Speaks the stream-json protocol of `claude -p`: answers each message with « n:<count> <first word> »."""
import json
import sys

n = 0
for line in sys.stdin:
    msg = json.loads(line)["message"]["content"]
    n += 1
    if "CRASH" in msg:
        sys.exit(1)
    print(json.dumps({"type": "system"}), flush=True)
    print(json.dumps({"type": "result", "is_error": "ERR" in msg, "result": f"n:{n} {msg.split()[0]}"}), flush=True)
