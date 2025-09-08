#!/usr/bin/env python3
"""
URL Resolver: converts internal storage URLs to externally exposed URLs.
Swap implementation later for S3/signed URLs without touching service logic.
"""

from typing import Optional


class UrlResolver:
    """Utility for converting internal file URLs to public API URLs"""

    @staticmethod
    def to_public(internal_url: str) -> str:
        """
        Convert internal file:// URLs to public /files/reports/ URLs.
        Other URLs pass through unchanged.
        
        Args:
            internal_url: Internal URL (typically file://)
            
        Returns:
            Public URL suitable for API responses
        """
        if not internal_url:
            return internal_url
            
        if internal_url.startswith("file://"):
            # Extract filename from file path
            file_path = internal_url.replace("file://", "")
            filename = file_path.split("/")[-1]  # Get last part of path
            
            # Convert to CSV if it's JSON
            if filename.endswith(".json"):
                filename = filename.replace(".json", ".csv")
                
            return f"/files/reports/{filename}"
        
        # Return unchanged for non-file URLs
        return internal_url
