"""Copy one correction-thread screenshot after the Aaron→Max 6B review migrate.

Requires:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

Usage:
    python scripts/copy_migrated_screenshot.py
"""

from __future__ import annotations

import os
import sys

from supabase import create_client

BUCKET = "case-files"
OLD_PATH = (
    "efef3d11-b11a-4e39-85a1-accdf52c03b2/"
    "bc3dd073-6740-41e2-9d2a-ee003486ab05/"
    "screenshots/9362e427-0b71-4229-b10b-3c939df8a11f/"
    "screenshot_1786398768567_1.png"
)
NEW_PATH = (
    "8eb8ec87-0c04-42ab-a9de-bbd37237f918/"
    "c8075dc1-72e7-4c10-8a6e-791a7349a066/"
    "screenshots/9362e427-0b71-4229-b10b-3c939df8a11f/"
    "screenshot_1786398768567_1.png"
)
SCREENSHOT_ID = "8e3d5de6-464b-47e4-8fdf-dd429508fa60"


def main() -> int:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.", file=sys.stderr)
        return 2

    client = create_client(url, key)
    data = client.storage.from_(BUCKET).download(OLD_PATH)
    if not data:
        print(f"Download failed for {OLD_PATH}", file=sys.stderr)
        return 1

    client.storage.from_(BUCKET).upload(
        NEW_PATH,
        data,
        file_options={
            "content-type": "image/png",
            "upsert": "true",
        },
    )
    (
        client.table("correction_thread_screenshots")
        .update({"storage_path": NEW_PATH})
        .eq("id", SCREENSHOT_ID)
        .execute()
    )
    print(f"Copied screenshot → {NEW_PATH}")
    print(f"Updated correction_thread_screenshots.id={SCREENSHOT_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
