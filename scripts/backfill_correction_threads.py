"""One-off backfill: legacy per-revision corrections -> correction threads.

Groups existing correction rows into threads:
- Rows linked by rolled_from_correction_id belong to the same thread.
- Roots sharing (case_id, section, normalized body) also collapse together.
- The earliest row becomes the thread's created_at and its 'raised' event.
- Later rows become 'still_open' (or 'resolved') events on their revision.
- Screenshots are re-linked to the thread (same storage objects, new rows).

Idempotent: the thread id reuses the root correction's uuid, and events are
only written for threads that have none yet. Old tables are never modified.

DRY RUN by default; pass --apply to write.

Environment:
    SUPABASE_URL                project URL
    SUPABASE_SERVICE_ROLE_KEY   service-role key (bypasses RLS)

Usage:
    python scripts/backfill_correction_threads.py            # dry run
    python scripts/backfill_correction_threads.py --apply    # write
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from typing import Any

from supabase import create_client


def normalized(body: str | None) -> str:
    return " ".join((body or "").split()).strip().lower()


def fetch_rows(client: Any) -> list[dict[str, Any]]:
    """All corrections with their section/revision context and screenshots."""
    revisions = (
        client.table("revisions")
        .select(
            "id, case_id, revision_no, status, "
            "revision_sections(id, section_key, "
            "corrections(id, body, status, rolled_from_correction_id, "
            "created_at, resolved_at, "
            "correction_screenshots(id, storage_path, original_filename, "
            "mime_type, size_bytes, uploaded_by, created_at)))"
        )
        .execute()
        .data
        or []
    )
    rows: list[dict[str, Any]] = []
    for revision in revisions:
        for section in revision.get("revision_sections") or []:
            for correction in section.get("corrections") or []:
                rows.append(
                    {
                        "id": correction["id"],
                        "case_id": revision["case_id"],
                        "revision_id": revision["id"],
                        "revision_no": revision["revision_no"],
                        "section": section["section_key"],
                        "body": correction.get("body") or "",
                        "status": correction.get("status") or "open",
                        "rolled_from": correction.get("rolled_from_correction_id"),
                        "created_at": correction.get("created_at") or "",
                        "resolved_at": correction.get("resolved_at"),
                        "screenshots": correction.get("correction_screenshots")
                        or [],
                    }
                )
    return rows


def group_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[list[dict[str, Any]]], list[dict[str, Any]]]:
    """Group corrections into thread candidates.

    Returns (groups, ambiguous_rows). Ambiguous rows are duplicates raised in
    the SAME revision with the same body: they are kept as their own thread
    but reported for manual review.
    """
    by_id = {row["id"]: row for row in rows}

    def root_of(row: dict[str, Any]) -> dict[str, Any]:
        current = row
        seen = set()
        while current["rolled_from"] and current["rolled_from"] in by_id:
            if current["id"] in seen:  # defensive: broken cycle
                break
            seen.add(current["id"])
            current = by_id[current["rolled_from"]]
        return current

    chains: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        chains[root_of(row)["id"]].append(row)

    # Merge roots that share case + section + normalized body.
    merged: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for root_id, members in chains.items():
        root = by_id[root_id]
        merged[
            (root["case_id"], root["section"], normalized(root["body"]))
        ].append(root_id)

    groups: list[list[dict[str, Any]]] = []
    ambiguous: list[dict[str, Any]] = []
    for root_ids in merged.values():
        members: list[dict[str, Any]] = []
        for root_id in root_ids:
            members.extend(chains[root_id])
        members.sort(key=lambda row: (row["revision_no"], row["created_at"]))
        seen_revisions: set[str] = set()
        for row in members:
            if row["revision_id"] in seen_revisions and row["rolled_from"] is None:
                ambiguous.append(row)
            seen_revisions.add(row["revision_id"])
        groups.append(members)
    return groups, ambiguous


def plan_thread(members: list[dict[str, Any]]) -> dict[str, Any]:
    first = members[0]
    last = members[-1]
    resolved = last["status"] == "resolved"
    events: list[dict[str, Any]] = [
        {
            "thread_id": first["id"],
            "revision_id": first["revision_id"],
            "event_type": "raised",
            "body": first["body"],
            "created_at": first["created_at"],
        }
    ]
    for row in members[1:]:
        events.append(
            {
                "thread_id": first["id"],
                "revision_id": row["revision_id"],
                "event_type": (
                    "resolved" if row["status"] == "resolved" else "still_open"
                ),
                "body": None,
                "created_at": row["created_at"],
            }
        )
    if resolved and len(members) == 1:
        events.append(
            {
                "thread_id": first["id"],
                "revision_id": last["revision_id"],
                "event_type": "resolved",
                "body": None,
                "created_at": last["resolved_at"] or last["created_at"],
            }
        )
    screenshots: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for row in members:
        for shot in row["screenshots"]:
            if shot["storage_path"] in seen_paths:
                continue
            seen_paths.add(shot["storage_path"])
            screenshots.append(
                {
                    "id": shot["id"],
                    "thread_id": first["id"],
                    "storage_path": shot["storage_path"],
                    "original_filename": shot["original_filename"],
                    "mime_type": shot.get("mime_type"),
                    "size_bytes": shot.get("size_bytes"),
                    "uploaded_by": shot.get("uploaded_by"),
                    "created_at": shot.get("created_at"),
                }
            )
    return {
        "thread": {
            "id": first["id"],  # reusing the root uuid keeps this idempotent
            "case_id": first["case_id"],
            "section": first["section"],
            "status": "resolved" if resolved else "open",
            "created_at": first["created_at"],
            "resolved_at": last["resolved_at"] if resolved else None,
            "resolved_in_revision_id": last["revision_id"] if resolved else None,
        },
        "events": events,
        "screenshots": screenshots,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write threads/events (default is dry run).",
    )
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.")
        return 2

    client = create_client(url, key)
    rows = fetch_rows(client)
    groups, ambiguous = group_rows(rows)
    plans = [plan_thread(members) for members in groups]

    existing = {
        row["id"]
        for row in (
            client.table("corrections_threads").select("id").execute().data or []
        )
    }
    new_plans = [
        plan for plan in plans if plan["thread"]["id"] not in existing
    ]

    print(f"Corrections scanned:   {len(rows)}")
    print(f"Threads planned:       {len(plans)}")
    print(f"Already backfilled:    {len(plans) - len(new_plans)}")
    print(f"Threads to create:     {len(new_plans)}")
    print(f"Events to create:      {sum(len(p['events']) for p in new_plans)}")
    print(
        f"Screenshots to link:   {sum(len(p['screenshots']) for p in new_plans)}"
    )
    if ambiguous:
        print(f"\nRows needing manual review ({len(ambiguous)}):")
        for row in ambiguous:
            print(
                f"  correction {row['id']} · case {row['case_id']} · "
                f"{row['section']} · rev {row['revision_no']} · "
                f"{row['body'][:60]!r}"
            )

    if not args.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply to write.")
        return 0

    for plan in new_plans:
        client.table("corrections_threads").insert(plan["thread"]).execute()
        client.table("correction_events").insert(plan["events"]).execute()
        if plan["screenshots"]:
            client.table("correction_thread_screenshots").insert(
                plan["screenshots"]
            ).execute()
    print(f"\nWrote {len(new_plans)} threads.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
