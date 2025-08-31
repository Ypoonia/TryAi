#!/usr/bin/env python3
"""
URL Resolver: converts internal storage URLs to externally exposed URLs.
Swap implementation later for S3/signed URLs without touching service logic.
"""

from typing import Optional


class UrlResolver:
    def to_public(self, internal: Optional[str]) -> Optional[str]:
        if not internal:
            return None
        # Current rule: file://.../reports/<name>.json -> /files/reports/<name>.csv
        if internal.startswith("file://"):
            path = internal.replace("file://", "")
            if "reports/" in path:
                filename = path.split("reports/")[-1]
                if filename.endswith(".json"):
                    filename = filename[:-5] + ".csv"
                return f"/files/reports/{filename}"
        return internal
