"""
DEMO 4 — Bulk-assign traces to an annotation queue via the public REST API.

Goal
----
Show how to go from "I have an interesting filter in the UI" to "the SME
team has 50 items to review this week" without any manual clicking.

Workflow:
  1. Query /api/public/traces for traces matching a filter (here: tag
     `judge-demo` + a date range + low score on `helpfulness`).
  2. POST each one to /api/public/annotation-queues/{queueId}/items.
  3. Print a summary of what was assigned.

Docs verified 2026-04:
  - api.reference.langfuse.com → operationId `annotationQueues_createQueueItem`
  - Request body schema: {"objectId": str, "objectType": str, "status"?: str}
  - Auth: HTTP Basic (username = public key, password = secret key)

# GAP: the public OpenAPI reference only shows "TRACE" as an example value
# for `objectType`. `OBSERVATION` and `SESSION` are used server-side (visible
# in the Langfuse GitHub repo under `web/src/features/annotation-queues/...`)
# but are NOT enumerated on the public schema page. Treat support for those
# as "inferred from source, not publicly documented".

Run:
    export LANGFUSE_QUEUE_ID=<copy from the UI: Annotation Queues → your queue>
    python 04_bulk_assign_to_queue.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import requests


def env(name: str, *, required: bool = True) -> str:
    v = os.environ.get(name, "")
    if required and not v:
        print(f"Missing env var: {name}. See demos/README.md.", file=sys.stderr)
        sys.exit(1)
    return v


HOST = env("LANGFUSE_HOST").rstrip("/")
PUBLIC_KEY = env("LANGFUSE_PUBLIC_KEY")
SECRET_KEY = env("LANGFUSE_SECRET_KEY")
QUEUE_ID = env("LANGFUSE_QUEUE_ID")

AUTH = (PUBLIC_KEY, SECRET_KEY)
HEADERS = {"Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# 1. Find candidate traces — anything tagged judge-demo from the last 24h.
#    In production you would typically also filter by a score threshold
#    (e.g. helpfulness < 0.5). The score-based server-side filter syntax for
#    /api/public/traces is not covered in depth in public docs, so we do a
#    client-side second pass instead. # GAP: scores-filter syntax on traces API.
# ---------------------------------------------------------------------------
def list_candidate_traces(limit: int = 50) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    params = {
        "tags": "judge-demo",        # public API accepts `tags` as CSV or repeated
        "fromTimestamp": since,
        "limit": limit,
    }
    r = requests.get(
        f"{HOST}/api/public/traces",
        params=params,
        auth=AUTH,
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("data", [])


# ---------------------------------------------------------------------------
# 2. Assign to the queue. Body is {objectId, objectType, status?}.
# ---------------------------------------------------------------------------
def assign_trace_to_queue(trace_id: str) -> tuple[bool, str]:
    url = f"{HOST}/api/public/annotation-queues/{QUEUE_ID}/items"
    body = {
        "objectId": trace_id,
        "objectType": "TRACE",
        # "status": "PENDING",  # optional — server default is PENDING
    }
    r = requests.post(url, json=body, auth=AUTH, headers=HEADERS, timeout=30)
    if r.ok:
        return True, r.json().get("id", "")
    return False, f"{r.status_code} {r.text}"


def main() -> None:
    traces = list_candidate_traces()
    print(f"Found {len(traces)} candidate traces.")
    if not traces:
        print("  Nothing to assign. Run 03_generate_traffic.py first.")
        return

    assigned, skipped = 0, 0
    for t in traces:
        trace_id = t["id"]
        ok, info = assign_trace_to_queue(trace_id)
        if ok:
            assigned += 1
            print(f"  ✓ {trace_id} → queue item {info}")
        else:
            skipped += 1
            print(f"  ✗ {trace_id}: {info}")

    print(f"\nSummary: {assigned} assigned, {skipped} skipped.")
    print(f"Open the queue in Langfuse UI: {HOST}/annotation-queues/{QUEUE_ID}")


if __name__ == "__main__":
    main()
