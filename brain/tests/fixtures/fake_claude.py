"""Speaks the stream-json protocol of `claude -p`: answers each message with « n:<count> <first word> » (in two pieces)."""
import json
import sys

n = 0
for line in sys.stdin:
    msg = json.loads(line)["message"]["content"]
    n += 1
    if "CRASH" in msg:
        sys.exit(1)
    text = f"n:{n} {msg.split()[0]}"
    print(json.dumps({"type": "system"}), flush=True)
    for piece in (text[:3], text[3:]):
        print(json.dumps({"type": "stream_event", "event": {"delta": {"type": "text_delta", "text": piece}}}), flush=True)
    print(json.dumps({"type": "result", "is_error": "ERR" in msg, "result": text}), flush=True)
