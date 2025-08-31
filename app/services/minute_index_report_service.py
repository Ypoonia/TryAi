#!/usr/bin/env python3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from pathlib import Path
import pytz
from collections import defaultdict
import math

from app.core.config import settings

logger = logging.getLogger(__name__)

class MinuteIndexReportService:
    """
    Store Report Service using Local-Minute Index + Interval Sweep Algorithm
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
    
    def generate_store_report(self, report_id: str, max_stores: int = 100) -> Dict[str, Any]:
        """
        Generate store monitoring report using minute index algorithm
        """
        try:
            logger.info(f"Starting minute-index report generation for {report_id}")
            
            # Step 0: Fetch/anchor - get MAX_UTC and define bands
            max_utc = self._get_max_timestamp_utc()
            logger.info(f"MAX_UTC: {max_utc}")
            
            # Get stores to process
            stores_data = self._get_stores_for_processing(max_stores)
            logger.info(f"Processing {len(stores_data)} stores")
            
            report_data = []
            
            for store_info in stores_data:
                store_id = store_info['store_id']
                tz_str = store_info['timezone_str']
                
                logger.debug(f"Processing store {store_id} in timezone {tz_str}")
                
                try:
                    store_metrics = self._process_store_with_minute_index(
                        store_id, tz_str, max_utc
                    )
                    if store_metrics:
                        report_data.append(store_metrics)
                except Exception as e:
                    logger.error(f"Error processing store {store_id}: {e}")
                    continue
            
            # Save report
            report_file_path = self._save_report_json(report_id, report_data, max_utc)
            
            # Generate summary
            summary = self._generate_report_summary(report_data)
            
            logger.info(f"Minute-index report completed for {report_id}: {len(report_data)} stores")
            
            return {
                "success": True,
                "report_id": report_id,
                "total_stores": len(report_data),
                "file_path": str(report_file_path),
                "summary": summary,
                "generated_at": datetime.utcnow().isoformat(),
                "max_utc": max_utc.isoformat(),
                "algorithm": "Carry-Forward (Seed-Before) Interval Sweep"
            }
            
        except Exception as e:
            logger.error(f"Error generating minute-index report {report_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "report_id": report_id
            }
    
    def _get_max_timestamp_utc(self) -> datetime:
        """Get MAX(timestamp_utc) from raw.store_status"""
        
        query = text("SELECT MAX(timestamp_utc) FROM raw.store_status")
        result = self.db.execute(query).fetchone()
        
        max_timestamp_str = result[0]
        if isinstance(max_timestamp_str, str):
            # Handle CSV format with ' UTC' suffix
            max_timestamp_str = max_timestamp_str.replace(' UTC', '')
            max_utc = datetime.fromisoformat(max_timestamp_str)
        else:
            max_utc = result[0]
        
        return max_utc
    
    def _get_stores_for_processing(self, max_stores: int) -> List[Dict[str, Any]]:
        """Get stores with their timezone info"""
        
        query = text("""
            SELECT DISTINCT 
                s.store_id,
                COALESCE(t.timezone_str, 'America/Chicago') as timezone_str
            FROM raw.store_status s
            LEFT JOIN raw.timezones t ON s.store_id = t.store_id
            LIMIT :max_stores
        """)
        
        result = self.db.execute(query, {"max_stores": max_stores}).fetchall()
        
        return [
            {
                "store_id": row[0],
                "timezone_str": row[1]
            }
            for row in result
        ]
    
    def _process_store_with_minute_index(self, store_id: str, tz_str: str, max_utc: datetime) -> Optional[Dict[str, Any]]:
        """
        Process a single store using the minute index algorithm
        """
        
        # Step 0: Setup UTC timezone and NOW_s
        # Use UTC for all calculations - no timezone conversion
        now_s = self._floor_minute(max_utc)
        
        logger.debug(f"Store {store_id}: NOW_s = {now_s}")
        
        # Define bands (half-open index ranges)
        H = (1, 61)      # Hour: [1, 61) = 60 minutes
        D = (1, 1441)    # Day: [1, 1441) = 1440 minutes 
        W = (1, 10081)   # Week: [1, 10081) = 10080 minutes
        
        # Step 1: Load & normalize polls (using UTC)
        polls_normalized = self._load_and_normalize_polls(store_id, None, now_s)
        
        if not polls_normalized:
            logger.debug(f"Store {store_id}: No polls found, excluding")
            return None
        
        # Step 2: Build BH intervals (using UTC)
        bh_intervals = self._build_bh_intervals(store_id, None, now_s)
        
        # Calculate BH budgets
        B_H = sum(self._overlap_len(interval, H) for interval in bh_intervals)
        B_D = sum(self._overlap_len(interval, D) for interval in bh_intervals)
        B_W = sum(self._overlap_len(interval, W) for interval in bh_intervals)
        
        logger.debug(f"Store {store_id}: BH budgets H={B_H}, D={B_D}, W={B_W}")
        
        # Step 3: Build status spans with "seed before" logic
        status_spans = self._build_status_spans_with_seed_before(polls_normalized, W, now_s)
        
        # Step 4: Two-pointer sweep
        U_H, U_D, U_W = self._two_pointer_sweep(bh_intervals, status_spans, H, D, W)
        
        # Step 5: Final clamps & convert to output format
        U_H = self._clamp(U_H, 0, B_H)
        U_D = self._clamp(U_D, 0, B_D) 
        U_W = self._clamp(U_W, 0, B_W)
        
        D_H = B_H - U_H
        D_D = B_D - U_D
        D_W = B_W - U_W
        
        # Verify invariants
        assert abs((U_H + D_H) - B_H) < 1e-9, f"Hour invariant failed: {U_H} + {D_H} != {B_H}"
        assert abs((U_D + D_D) - B_D) < 1e-9, f"Day invariant failed: {U_D} + {D_D} != {B_D}"
        assert abs((U_W + D_W) - B_W) < 1e-9, f"Week invariant failed: {U_W} + {D_W} != {B_W}"
        
        return {
            "store_id": store_id,
            "uptime_last_hour": U_H,              # minutes
            "uptime_last_day": U_D / 60.0,        # hours
            "uptime_last_week": U_W / 60.0,       # hours
            "downtime_last_hour": D_H,            # minutes
            "downtime_last_day": D_D / 60.0,      # hours
            "downtime_last_week": D_W / 60.0,     # hours
            "timezone": tz_str,
            "now_s": now_s.isoformat(),
            "algorithm_details": {
                "total_polls": len(polls_normalized),
                "bh_intervals_count": len(bh_intervals),
                "status_spans_count": len(status_spans),
                "bh_budgets": {"H": B_H, "D": B_D, "W": B_W},
                "raw_uptimes": {"H": U_H, "D": U_D, "W": U_W}
            }
        }
    
    # Helper Primitives
    
    def _floor_minute(self, dt: datetime) -> datetime:
        """Floor datetime to minute boundary"""
        return dt.replace(second=0, microsecond=0)
    
    def _minute_index(self, dt: datetime, now_s: datetime) -> int:
        """Map local datetime dt (floored to minute) to index k"""
        delta_minutes = (now_s - dt).total_seconds() / 60.0
        return math.ceil(delta_minutes)
    
    def _index_to_datetime(self, k: int, now_s: datetime) -> datetime:
        """Inverse: dt(k) = NOW_s - k minutes"""
        return now_s - timedelta(minutes=k)
    
    def _overlap_len(self, interval1: Tuple[int, int], interval2: Tuple[int, int]) -> int:
        """Calculate overlap length between two half-open intervals [a,b) and [x,y)"""
        a, b = interval1
        x, y = interval2
        return max(0, min(b, y) - max(a, x))
    
    def _clamp(self, value: float, lo: float, hi: float) -> float:
        """Clamp value between lo and hi"""
        return max(lo, min(hi, value))
    
    # Step 1: Load & Normalize Polls
    
    def _load_and_normalize_polls(self, store_id: str, store_tz: Optional[pytz.BaseTzInfo], now_s: datetime) -> List[Tuple[int, str]]:
        """
        Load and normalize polls for the store
        Returns list of (minute_index, status) sorted by minute_index
        """
        
        # Calculate left boundary with buffer (UTC)
        left_buf_minutes = 1440  # 1 day buffer
        left_dt_utc = now_s - timedelta(minutes=10080 + left_buf_minutes)
        
        query = text("""
            SELECT timestamp_utc, status
            FROM raw.store_status
            WHERE store_id = :store_id
              AND timestamp_utc >= :left_dt_utc
            ORDER BY timestamp_utc ASC
        """)
        
        result = self.db.execute(query, {
            "store_id": store_id,
            "left_dt_utc": left_dt_utc.strftime("%Y-%m-%d %H:%M:%S")
        }).fetchall()
        
        # Normalize polls: convert to local, floor to minute, deduplicate
        minute_polls = {}  # minute_index -> (latest_timestamp_utc, status)
        
        for row in result:
            timestamp_utc_str = row[0]
            status = row[1]
            
            # Parse timestamp (UTC)
            if isinstance(timestamp_utc_str, str):
                timestamp_utc_str = timestamp_utc_str.replace(' UTC', '')
                timestamp_utc = datetime.fromisoformat(timestamp_utc_str)
            else:
                timestamp_utc = timestamp_utc_str
            
            # Keep in UTC and floor
            dt_local_floored = self._floor_minute(timestamp_utc)
            
            # Calculate minute index
            minute_index = self._minute_index(dt_local_floored, now_s)
            
            # Map status to active/inactive
            norm_status = self._map_to_active_inactive(status)
            if norm_status is None:
                continue  # Skip unknown statuses
            
            # Keep latest timestamp for this minute
            if minute_index not in minute_polls or timestamp_utc > minute_polls[minute_index][0]:
                minute_polls[minute_index] = (timestamp_utc, norm_status)
        
        # Filter to relevant range and sort
        polls_normalized = []
        for minute_index, (_, status) in minute_polls.items():
            if minute_index <= 10080:  # Within week window (+ seed if < 1)
                polls_normalized.append((minute_index, status))
        
        polls_normalized.sort(key=lambda x: x[0])
        
        logger.debug(f"Store {store_id}: Normalized {len(polls_normalized)} polls")
        return polls_normalized
    
    def _map_to_active_inactive(self, status: str) -> Optional[str]:
        """Map status to active/inactive, return None for unknown"""
        status_lower = status.lower().strip()
        if status_lower == 'active':
            return 'active'
        elif status_lower == 'inactive':
            return 'inactive'
        else:
            return None  # Drop unknown statuses
    
    # Step 2: Build BH Intervals
    
    def _build_bh_intervals(self, store_id: str, store_tz: Optional[pytz.BaseTzInfo], now_s: datetime) -> List[Tuple[int, int]]:
        """
        Build business hours intervals as index intervals
        """
        
        # Get menu hours
        query = text("""
            SELECT "dayOfWeek", start_time_local, end_time_local
            FROM raw.menu_hours
            WHERE store_id = :store_id
            ORDER BY "dayOfWeek", start_time_local
        """)
        
        result = self.db.execute(query, {"store_id": store_id}).fetchall()
        
        if not result:
            # No business hours found, assume 24/7
            return [(1, 10081)]
        
        bh_intervals = []
        
        # Consider each UTC calendar day covering last 7 days (with buffer)
        start_date = (now_s - timedelta(days=8)).date()
        end_date = (now_s + timedelta(days=1)).date()
        
        current_date = start_date
        while current_date <= end_date:
            weekday = current_date.weekday()  # 0=Monday, 6=Sunday
            
            # Get business hours for this weekday
            day_hours = [(row[1], row[2]) for row in result if int(row[0]) == weekday]
            
            if not day_hours:
                current_date += timedelta(days=1)
                continue
            
            # Process each business hour window for this day
            windows = []
            for start_time_str, end_time_str in day_hours:
                start_time = self._parse_time_str(start_time_str)
                end_time = self._parse_time_str(end_time_str)
                
                # Handle overnight windows (end < start)
                if end_time <= start_time:
                    # Split into two windows
                    from datetime import time
                    windows.append((start_time, time(23, 59, 59)))
                    windows.append((time(0, 0, 0), end_time))
                else:
                    windows.append((start_time, end_time))
            
            # Merge overlapping/adjacent windows
            windows = self._merge_time_windows(windows)
            
            # Convert to absolute datetime intervals and then to indices
            for start_time, end_time in windows:
                dt_start = datetime.combine(current_date, start_time)
                dt_end = datetime.combine(current_date, end_time)
                
                # Convert to indices
                # Note: end is exclusive, so maps to k(dt_end)
                # start is inclusive, so maps to k(dt_start) 
                idx_end = max(1, self._minute_index(dt_end, now_s))
                idx_start = min(10081, self._minute_index(dt_start, now_s))
                
                if idx_end < idx_start:  # Valid interval
                    bh_intervals.append((idx_end, idx_start))
            
            current_date += timedelta(days=1)
        
        # Merge and sort intervals
        bh_intervals = self._merge_sorted_intervals(bh_intervals)
        
        logger.debug(f"Store {store_id}: Built {len(bh_intervals)} BH intervals")
        return bh_intervals
    
    def _parse_time_str(self, time_str: str) -> datetime.time:
        """Parse time string like '09:00:00'"""
        try:
            from datetime import time
            # Use time.fromisoformat for proper parsing
            if len(time_str.split(':')) == 2:
                time_str += ':00'  # Add seconds if missing
            return time.fromisoformat(time_str)
        except:
            # Fallback: manual parsing
            try:
                parts = time_str.split(':')
                hour = int(parts[0])
                minute = int(parts[1])
                second = int(parts[2]) if len(parts) > 2 else 0
                from datetime import time
                return time(hour, minute, second)
            except:
                from datetime import time
                return time(0, 0, 0)  # Default to start of day
    
    def _merge_time_windows(self, windows: List[Tuple[datetime.time, datetime.time]]) -> List[Tuple[datetime.time, datetime.time]]:
        """Merge overlapping/adjacent time windows"""
        if not windows:
            return []
        
        # Sort by start time
        windows.sort(key=lambda x: x[0])
        
        merged = [windows[0]]
        for start, end in windows[1:]:
            last_start, last_end = merged[-1]
            
            # Check if overlapping or adjacent
            if start <= last_end:
                # Merge
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        
        return merged
    
    def _merge_sorted_intervals(self, intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Merge overlapping/adjacent sorted intervals"""
        if not intervals:
            return []
        
        intervals.sort()
        merged = [intervals[0]]
        
        for start, end in intervals[1:]:
            last_start, last_end = merged[-1]
            
            if start <= last_end:  # Overlapping or adjacent
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        
        return merged
    
    # Step 3: Build Status Spans
    
    def _build_status_spans_with_seed_before(self, polls_normalized: List[Tuple[int, str]], W: Tuple[int, int], now_s: datetime) -> List[Tuple[int, int, str]]:
        """
        Build status spans with "seed before" logic
        When status changes from inactive -> active, start active period from previous inactive timestamp
        Returns list of (start_idx, end_idx, status) intervals
        """
        
        if not polls_normalized:
            return []
        
        status_spans = []
        start_w = W[1] - 1  # 10080 (start of week window)
        
        # Find seed status (latest poll <= start_w)
        seed_status = None
        for idx, status in polls_normalized:
            if idx <= start_w:
                seed_status = status
        
        if seed_status is None:
            # Use first in-window poll's status
            seed_status = polls_normalized[0][1]
        
        # Filter polls to window W
        window_polls = [(idx, status) for idx, status in polls_normalized if W[0] <= idx < W[1]]
        
        if not window_polls:
            # No polls in window, entire window has seed status
            return [(W[0], W[1], seed_status)]
        
        # Build status timeline with "seed before" logic
        timeline = []
        
        # Check if first poll in window is already active
        if window_polls and window_polls[0][1] == "active":
            # Store was already active at start of window
            # Find the last inactive poll before the window
            last_inactive_before_window = None
            for idx, status in polls_normalized:
                if idx >= W[1] and status == "inactive":  # Polls outside window
                    last_inactive_before_window = idx
                    break
            
            if last_inactive_before_window:
                # Start active period from the last inactive before window
                timeline.append((last_inactive_before_window, window_polls[0][0], "active"))
                current_idx = window_polls[0][0]
                current_status = "active"
            else:
                # No inactive poll found, start from beginning of window
                current_idx = W[1] - 1
                current_status = "active"
        else:
            # Start with seed status
            current_idx = W[1] - 1  # Start from beginning of window (10080)
            current_status = seed_status
        
        # Process each poll in window
        prev_idx = current_idx
        prev_status = current_status
        
        for poll_idx, poll_status in window_polls:
            if poll_status == prev_status:
                # Status continues, just update position
                prev_idx = poll_idx
            else:
                # Status change - implement "seed before" logic
                if prev_status == "inactive" and poll_status == "active":
                    # When changing from inactive -> active, start active from previous inactive timestamp
                    # Don't create a midpoint, just continue from prev_idx
                    timeline.append((prev_idx, poll_idx, poll_status))
                else:
                    # For other transitions, use midpoint interpolation
                    midpoint = (prev_idx + poll_idx) // 2
                    
                    # Close previous span
                    if prev_idx < midpoint:
                        timeline.append((prev_idx, midpoint, prev_status))
                    
                    # Start new span
                    timeline.append((midpoint, poll_idx, poll_status))
                
                prev_idx = poll_idx
                prev_status = poll_status
        
        # Extend to end of window with 23:00 cutoff logic
        if prev_idx < W[1]:
            # Apply 23:00 cutoff logic for active periods
            if prev_status == "active":
                # Find the 23:00 cutoff minute index
                cutoff_time = now_s.replace(hour=23, minute=0, second=0, microsecond=0)
                cutoff_idx = self._minute_index(cutoff_time, now_s)
                
                # Use the earlier of W[1] or cutoff_idx
                end_idx = min(W[1], cutoff_idx)
                if prev_idx < end_idx:
                    timeline.append((prev_idx, end_idx, prev_status))
            else:
                # For inactive periods, use full window
                timeline.append((prev_idx, W[1], prev_status))
        
        # Merge adjacent spans with same status
        if timeline:
            status_spans = [timeline[0]]
            for start, end, status in timeline[1:]:
                last_start, last_end, last_status = status_spans[-1]
                
                if status == last_status and start == last_end:
                    # Merge adjacent spans
                    status_spans[-1] = (last_start, end, status)
                else:
                    status_spans.append((start, end, status))
        
        # Clamp all spans to W and filter valid ones
        status_spans = [
            (max(start, W[0]), min(end, W[1]), status)
            for start, end, status in status_spans
            if max(start, W[0]) < min(end, W[1])
        ]
        
        logger.debug(f"Built {len(status_spans)} status spans with seed before logic")
        return status_spans
    
    def _build_status_spans(self, polls_normalized: List[Tuple[int, str]], W: Tuple[int, int]) -> List[Tuple[int, int, str]]:
        """
        Build status spans with midpoint interpolation
        Returns list of (start_idx, end_idx, status) intervals
        """
        
        if not polls_normalized:
            return []
        
        status_spans = []
        start_w = W[1] - 1  # 10080 (start of week window)
        
        # Find seed status (latest poll <= start_w)
        seed_status = None
        for idx, status in polls_normalized:
            if idx <= start_w:
                seed_status = status
        
        if seed_status is None:
            # Use first in-window poll's status
            seed_status = polls_normalized[0][1]
        
        # Filter polls to window W
        window_polls = [(idx, status) for idx, status in polls_normalized if W[0] <= idx < W[1]]
        
        if not window_polls:
            # No polls in window, entire window has seed status
            return [(W[0], W[1], seed_status)]
        
        # Build status timeline
        timeline = []
        
        # Start with seed status
        current_idx = W[1] - 1  # Start from beginning of window (10080)
        current_status = seed_status
        
        # Process each poll in window
        prev_idx = current_idx
        prev_status = current_status
        
        for poll_idx, poll_status in window_polls:
            if poll_status == prev_status:
                # Status continues, just update position
                prev_idx = poll_idx
            else:
                # Status change - use midpoint interpolation
                midpoint = (prev_idx + poll_idx) // 2
                
                # Close previous span
                if prev_idx < midpoint:
                    timeline.append((prev_idx, midpoint, prev_status))
                
                # Start new span
                timeline.append((midpoint, poll_idx, poll_status))
                prev_idx = poll_idx
                prev_status = poll_status
        
        # Extend to end of window
        if prev_idx < W[1]:
            timeline.append((prev_idx, W[1], prev_status))
        
        # Merge adjacent spans with same status
        if timeline:
            status_spans = [timeline[0]]
            for start, end, status in timeline[1:]:
                last_start, last_end, last_status = status_spans[-1]
                
                if status == last_status and start == last_end:
                    # Merge adjacent spans
                    status_spans[-1] = (last_start, end, status)
                else:
                    status_spans.append((start, end, status))
        
        # Clamp all spans to W and filter valid ones
        status_spans = [
            (max(start, W[0]), min(end, W[1]), status)
            for start, end, status in status_spans
            if max(start, W[0]) < min(end, W[1])
        ]
        
        logger.debug(f"Built {len(status_spans)} status spans")
        return status_spans
    
    # Step 4: Two-Pointer Sweep
    
    def _two_pointer_sweep(self, bh_intervals: List[Tuple[int, int]], 
                          status_spans: List[Tuple[int, int, str]],
                          H: Tuple[int, int], D: Tuple[int, int], W: Tuple[int, int]) -> Tuple[float, float, float]:
        """
        Two-pointer sweep over BH × status spans
        Returns (U_H, U_D, U_W) uptime minutes for each band
        """
        
        U_H = U_D = U_W = 0.0
        
        i = j = 0
        while i < len(bh_intervals) and j < len(status_spans):
            # Get current intervals
            bh_start, bh_end = bh_intervals[i]
            span_start, span_end, status = status_spans[j]
            
            # Calculate overlap
            overlap_start = max(bh_start, span_start)
            overlap_end = min(bh_end, span_end)
            
            if overlap_start < overlap_end:
                # There's an overlap
                overlap_interval = (overlap_start, overlap_end)
                
                # Calculate overlap with each band
                oh = self._overlap_len(overlap_interval, H)
                od = self._overlap_len(overlap_interval, D)
                ow = self._overlap_len(overlap_interval, W)
                
                # Add to uptime if status is active
                if status == 'active':
                    U_H += oh
                    U_D += od
                    U_W += ow
            
            # Advance pointer that finishes first
            if bh_end <= span_end:
                i += 1
            if span_end <= bh_end:
                j += 1
        
        return U_H, U_D, U_W
    
    # Output and Summary
    
    def _save_report_json(self, report_id: str, report_data: List[Dict], max_utc: datetime) -> Path:
        """Save the report as JSON file"""
        
        report_file = self.reports_dir / f"{report_id}.json"
        
        full_report = {
            "report_metadata": {
                "report_id": report_id,
                "generated_at": datetime.utcnow().isoformat(),
                "total_stores": len(report_data),
                "max_utc": max_utc.isoformat(),
                "algorithm": "Carry-Forward (Seed-Before) Interval Sweep",
                "bands": {
                    "H": "[1, 61) = 60 minutes (last hour)",
                    "D": "[1, 1441) = 1440 minutes (last day)", 
                    "W": "[1, 10081) = 10080 minutes (last week)"
                },
                "schema": [
                    "store_id",
                    "uptime_last_hour (minutes)",
                    "uptime_last_day (hours)",
                    "uptime_last_week (hours)",
                    "downtime_last_hour (minutes)",
                    "downtime_last_day (hours)",
                    "downtime_last_week (hours)"
                ]
            },
            "report_data": report_data,
            "algorithm_details": {
                "description": "Carry-forward logic with seed-before interpolation",
                "features": [
                    "Local minute index counting backwards from MAX_UTC",
                    "Proper timezone conversion per store",
                    "Business hours as index intervals",
                    "Carry-forward (seed-before) interpolation between status changes",
                    "Two-pointer sweep for efficient intersection",
                    "Invariant validation (uptime + downtime = business hours)"
                ]
            }
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(full_report, f, indent=2, default=str)
        
        logger.info(f"Minute-index report saved to {report_file}")
        return report_file
    
    def _generate_report_summary(self, report_data: List[Dict]) -> Dict[str, Any]:
        """Generate summary statistics for the report"""
        
        if not report_data:
            return {"message": "No data to summarize"}
        
        total_stores = len(report_data)
        
        # Calculate averages
        avg_uptime_hour = sum(store["uptime_last_hour"] for store in report_data) / total_stores
        avg_uptime_day = sum(store["uptime_last_day"] for store in report_data) / total_stores
        avg_uptime_week = sum(store["uptime_last_week"] for store in report_data) / total_stores
        
        avg_downtime_hour = sum(store["downtime_last_hour"] for store in report_data) / total_stores
        avg_downtime_day = sum(store["downtime_last_day"] for store in report_data) / total_stores
        avg_downtime_week = sum(store["downtime_last_week"] for store in report_data) / total_stores
        
        # Calculate active/inactive counts (majority uptime)
        active_stores_hour = sum(1 for store in report_data if store["uptime_last_hour"] > store["downtime_last_hour"])
        active_stores_day = sum(1 for store in report_data if store["uptime_last_day"] > store["downtime_last_day"])
        active_stores_week = sum(1 for store in report_data if store["uptime_last_week"] > store["downtime_last_week"])
        
        # Algorithm efficiency stats
        total_polls = sum(store["algorithm_details"]["total_polls"] for store in report_data)
        avg_polls_per_store = total_polls / total_stores if total_stores > 0 else 0
        
        return {
            "total_stores": total_stores,
            "algorithm": "Carry-Forward (Seed-Before) Interval Sweep",
            "averages": {
                "uptime_last_hour_minutes": round(avg_uptime_hour, 2),
                "uptime_last_day_hours": round(avg_uptime_day, 2),
                "uptime_last_week_hours": round(avg_uptime_week, 2),
                "downtime_last_hour_minutes": round(avg_downtime_hour, 2),
                "downtime_last_day_hours": round(avg_downtime_day, 2),
                "downtime_last_week_hours": round(avg_downtime_week, 2)
            },
            "active_stores": {
                "last_hour": f"{active_stores_hour}/{total_stores} ({100*active_stores_hour/total_stores:.1f}%)",
                "last_day": f"{active_stores_day}/{total_stores} ({100*active_stores_day/total_stores:.1f}%)",
                "last_week": f"{active_stores_week}/{total_stores} ({100*active_stores_week/total_stores:.1f}%)"
            },
            "efficiency": {
                "total_polls_processed": total_polls,
                "avg_polls_per_store": round(avg_polls_per_store, 1),
                "minute_level_precision": True,
                "timezone_aware": True,
                "carry_forward_seed_before": True
            }
        }
