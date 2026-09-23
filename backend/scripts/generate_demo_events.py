"""Send five matching failures to create a PulseForge demo incident."""

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def send_event(base_url: str, api_key: str, sequence: int) -> dict:
    payload = {
        "event_id": f"demo-{uuid.uuid4()}",
        "event_type": "DATABASE_TIMEOUT",
        "level": "CRITICAL" if sequence == 5 else "ERROR",
        "message": f"Payment database timed out (demo event {sequence}/5)",
        "occurred_at": (datetime.now(timezone.utc) + timedelta(seconds=sequence)).isoformat(),
        "metadata": {"database": "payments-db", "timeout_ms": 5000, "demo": True},
        "trace_id": f"demo-trace-{uuid.uuid4().hex[:12]}",
    }
    request = Request(
        f"{base_url.rstrip('/')}/api/v1/events",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", required=True, help="A non-revoked events:write API key")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    try:
        for sequence in range(1, 6):
            result = send_event(args.base_url, args.api_key, sequence)
            print(
                f"Sent {sequence}/5: event={result['event']['id']} "
                f"incident={result.get('incident_id')}"
            )
    except HTTPError as error:
        print(f"API returned {error.code}: {error.read().decode('utf-8')}", file=sys.stderr)
        return 1
    except URLError as error:
        print(f"Could not reach PulseForge: {error.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
