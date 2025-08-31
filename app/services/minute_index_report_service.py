#!/usr/bin/env python3
import json
import csv
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
            
            # Save JSON (metadata-rich, debugging)
            self._save_report_json(report_id, report_data, max_utc)
            
            # Save CSV (flat report for owners)
            report_file_path = self._save_report_csv(report_id, report_data, max_utc)
            
            # Generate summary
            summary = self._generate_report_summary(report_data)
            
            logger.info(f"Minute-index report completed for {report_id}: {len(report_data)} stores")
            
            return {
                "success": True,
                "report_id": report_id,
                "total_stores": len(report_data),
                "file_path": str(report_file_path),  # CSV path
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
        
        # Ensure timezone-aware UTC datetime (single source of truth)
        if max_utc.tzinfo is None:
            max_utc = pytz.UTC.localize(max_utc)
        
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
        
        # Step 0: Setup timezone and NOW_s in local timezone
        # Default to America/Chicago for US-based stores when timezone is missing
        # TODO: Consider geographic distribution analysis for better defaults
        store_tz = pytz.timezone(tz_str or "America/Chicago")
        now_s_local = self._floor_minute(max_utc.astimezone(store_tz))
        
        logger.debug(f"Store {store_id}: NOW_s_local = {now_s_local} (local timezone: {tz_str})")
        
        # Define bands (half-open index ranges)
        H = (1, 61)      # Hour: [1, 61) = 60 minutes
        D = (1, 1441)    # Day: [1, 1441) = 1440 minutes 
        W = (1, 10081)   # Week: [1, 10081) = 10080 minutes
        
        # Step 1: Load & normalize polls (using local timezone)
        polls_normalized = self._load_and_normalize_polls(store_id, store_tz, now_s_local)
        
        if not polls_normalized:
            logger.debug(f"Store {store_id}: No polls found, excluding")
            return None
        
        # Step 2: Build BH intervals (using local timezone)
        bh_intervals = self._build_bh_intervals(store_id, store_tz, now_s_local)
        
        # Calculate BH budgets
        B_H = sum(self._overlap_len(interval, H) for interval in bh_intervals)
        B_D = sum(self._overlap_len(interval, D) for interval in bh_intervals)
        B_W = sum(self._overlap_len(interval, W) for interval in bh_intervals)
        
        logger.debug(f"Store {store_id}: BH budgets H={B_H}, D={B_D}, W={B_W}")
        
        # Step 3: Build status spans with pure carry-forward logic
        status_spans = self._build_status_spans_carry_forward(polls_normalized, W)
        
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
            "now_s": now_s_local.isoformat(),
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
    
    def _minute_index(self, dt_local: datetime, now_s_local: datetime) -> int:
        """Map local datetime dt_local (floored to minute) to index k
        Both dt_local and now_s_local MUST be tz-aware in the SAME timezone"""
        delta_minutes = (now_s_local - dt_local).total_seconds() / 60.0
        return math.ceil(delta_minutes)
    
    def _index_to_datetime(self, k: int, now_s_local: datetime) -> datetime:
        """Inverse: dt(k) = now_s_local - k minutes"""
        return now_s_local - timedelta(minutes=k)
    
    def _overlap_len(self, interval1: Tuple[int, int], interval2: Tuple[int, int]) -> int:
        """Calculate overlap length between two half-open intervals [a,b) and [x,y)"""
        a, b = interval1
        x, y = interval2
        return max(0, min(b, y) - max(a, x))
    
    def _clamp(self, value: float, lo: float, hi: float) -> float:
        """Clamp value between lo and hi"""
        return max(lo, min(hi, value))
    
    # Step 1: Load & Normalize Polls
    
    def _load_and_normalize_polls(self, store_id: str, store_tz: Optional[pytz.BaseTzInfo], now_s_local: datetime) -> List[Tuple[int, str]]:
        """
        Load and normalize polls for the store
        Returns list of (minute_index, status) sorted by minute_index
        """
        
        # Calculate left boundary with buffer (local timezone)
        left_buf_minutes = 1440  # 1 day buffer
        left_dt_local = now_s_local - timedelta(minutes=10080 + left_buf_minutes)
        # left_dt_local is already timezone-aware, just convert to UTC
        left_dt_utc = left_dt_local.astimezone(pytz.UTC)
        
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
            
            # Parse timestamp (UTC) and ensure timezone-aware
            if isinstance(timestamp_utc_str, str):
                timestamp_utc_str = timestamp_utc_str.replace(' UTC', '')
                timestamp_utc = datetime.fromisoformat(timestamp_utc_str)
                if timestamp_utc.tzinfo is None:
                    timestamp_utc = pytz.UTC.localize(timestamp_utc)
            else:
                timestamp_utc = timestamp_utc_str
                if timestamp_utc.tzinfo is None:
                    timestamp_utc = pytz.UTC.localize(timestamp_utc)
            
            # Convert to local timezone (both dt_local and now_s_local are tz-aware in same tz)
            dt_local = timestamp_utc.astimezone(store_tz)
            dt_local_floored = self._floor_minute(dt_local)
            
            # Calculate minute index with both timezone-aware datetimes
            minute_index = self._minute_index(dt_local_floored, now_s_local)
            
            # Map status to active/inactive
            norm_status = self._map_to_active_inactive(status)
            if norm_status is None:
                continue  # Skip unknown statuses
            
            # Keep latest timestamp for this minute
            if minute_index not in minute_polls or timestamp_utc > minute_polls[minute_index][0]:
                minute_polls[minute_index] = (timestamp_utc, norm_status)
        
        # Keep all polls within buffer range (don't filter out pre-window polls for seeding)
        polls_normalized = []
        for minute_index, (_, status) in minute_polls.items():
            polls_normalized.append((minute_index, status))
        
        # Sort descending by index: larger index = older timestamp (chronological order)
        polls_normalized.sort(key=lambda x: x[0], reverse=True)
        
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
    
    def _build_bh_intervals(self, store_id: str, store_tz: Optional[pytz.BaseTzInfo], now_s_local: datetime) -> List[Tuple[int, int]]:
        """
        Build business hours intervals on local calendar days (IANA tz)
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
        
        # Build business hours by day
        bh_by_day = {}
        for row in result:
            day_of_week = int(row[0])
            start_time_str = row[1] 
            end_time_str = row[2]
            if day_of_week not in bh_by_day:
                bh_by_day[day_of_week] = []
            bh_by_day[day_of_week].append((start_time_str, end_time_str))
        
        bh_intervals = []
        
        # Iterate LOCAL midnights in store timezone (not UTC days)
        # Cover 8 days before to 1 day after to ensure full coverage
        start_date = (now_s_local - timedelta(days=8)).date()
        end_date = (now_s_local + timedelta(days=1)).date()
        
        current_date = start_date
        while current_date <= end_date:
            # Local midnight in store timezone
            local_midnight = datetime.combine(current_date, datetime.min.time())
            if store_tz:
                local_midnight = store_tz.localize(local_midnight)
            
            weekday = current_date.weekday()  # 0=Mon..6=Sun
            
            # Get business hours for this local day
            if weekday in bh_by_day:
                for start_time_str, end_time_str in bh_by_day[weekday]:
                    start_time = self._parse_time_str(start_time_str)
                    end_time = self._parse_time_str(end_time_str)
                    
                    # Create local datetime objects (tz-aware)
                    start_dt_local = datetime.combine(current_date, start_time)
                    end_dt_local = datetime.combine(current_date, end_time)
                    
                    if store_tz:
                        start_dt_local = store_tz.localize(start_dt_local)
                        end_dt_local = store_tz.localize(end_dt_local)
                    
                    # Handle overnight business hours (end < start)
                    if end_time <= start_time:
                        # Split overnight: two segments
                        # Segment 1: start_time to end of day
                        end_of_day = datetime.combine(current_date, datetime.max.time().replace(microsecond=0))
                        if store_tz:
                            end_of_day = store_tz.localize(end_of_day)
                        
                        idx_start1 = self._minute_index(start_dt_local, now_s_local)
                        idx_end1 = self._minute_index(end_of_day, now_s_local)
                        if idx_start1 > idx_end1:  # Valid interval (indices count backwards)
                            bh_intervals.append((idx_end1, idx_start1))
                        
                        # Segment 2: start of next day to end_time
                        next_date = current_date + timedelta(days=1)
                        start_of_next_day = datetime.combine(next_date, datetime.min.time())
                        end_dt_next = datetime.combine(next_date, end_time)
                        
                        if store_tz:
                            start_of_next_day = store_tz.localize(start_of_next_day)
                            end_dt_next = store_tz.localize(end_dt_next)
                        
                        idx_start2 = self._minute_index(start_of_next_day, now_s_local)
                        idx_end2 = self._minute_index(end_dt_next, now_s_local)
                        if idx_start2 > idx_end2:  # Valid interval
                            bh_intervals.append((idx_end2, idx_start2))
                    else:
                        # Normal hours within same day
                        idx_start = self._minute_index(start_dt_local, now_s_local)
                        idx_end = self._minute_index(end_dt_local, now_s_local)
                        if idx_start > idx_end:  # Valid interval (indices count backwards)
                            bh_intervals.append((idx_end, idx_start))
            
            current_date += timedelta(days=1)
        
        # Sort and merge overlapping intervals
        bh_intervals.sort()
        bh_intervals = self._merge_sorted_intervals(bh_intervals)
        
        logger.debug(f"Store {store_id}: Built {len(bh_intervals)} BH intervals")
        return bh_intervals
    
    def _parse_time_components(self, time_str: str) -> tuple:
        """Parse time string and return (hour, minute, second)"""
        try:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return hour, minute, second
        except:
            return 0, 0, 0  # Default to start of day
    
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
    
    def _build_status_spans_carry_forward(self, polls_idx: List[Tuple[int,str]], W: Tuple[int,int]) -> List[Tuple[int,int,str]]:
        """
        Pure carry-forward + seed-before timeline (no midpoint, no 23:00)
        polls_idx: (k, status) where k is minute index vs now_s_local
        """
        if not polls_idx:
            return [(W[0], W[1], 'inactive')]
        
        # seed = last poll at or BEFORE band start (k >= 10080)
        start_k = W[1]-1  # 10080
        seed_status = 'inactive'  # fallback
        for k, s in sorted(polls_idx, key=lambda x: x[0]):  # ascending k
            if k >= start_k:
                seed_status = s
                break
                
        # window polls (ascending k makes sense if you always create (min,max))
        window_polls = [(k,s) for (k,s) in polls_idx if W[0] <= k < W[1]]
        if not window_polls:
            return [(W[0], W[1], seed_status)]
            
        spans = []
        prev_k = start_k
        prev_s = seed_status
    
        # Iterate from window start toward now: use DESCENDING k for clarity
        for k, s in sorted(window_polls, key=lambda x: -x[0]):
            # segment between [k, prev_k) has status = prev_s (carry-forward)
            a, b = sorted((k, prev_k))
            if a < b:
                spans.append((a, b, prev_s))
            prev_k, prev_s = k, s
    
        # Tail to the window end (k=1)
        a, b = sorted((W[0], prev_k))
        if a < b:
            spans.append((a, b, prev_s))
    
        # Merge adjacents
        out = []
        for st, en, stt in sorted(spans):
            if out and out[-1][2] == stt and out[-1][1] == st:
                out[-1] = (out[-1][0], en, stt)
            else:
                out.append((st, en, stt))
        return out

    def _merge_sorted_intervals(self, intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Merge overlapping sorted intervals"""
        if not intervals:
            return []
        
        merged = [intervals[0]]
        for start, end in intervals[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged

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
    
    def _save_report_csv(self, report_id: str, report_data: List[Dict], max_utc: datetime) -> Path:
        """Save the report as CSV file"""
        report_file = self.reports_dir / f"{report_id}.csv"
        
        header = [
            "store_id",
            "uptime_last_hour (minutes)",
            "uptime_last_day (hours)",
            "uptime_last_week (hours)",
            "downtime_last_hour (minutes)",
            "downtime_last_day (hours)",
            "downtime_last_week (hours)",
            "timezone",
            "now_s"
        ]
        
        with open(report_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for store in report_data:
                writer.writerow([
                    store["store_id"],
                    store["uptime_last_hour"],
                    round(store["uptime_last_day"], 2),
                    round(store["uptime_last_week"], 2),
                    store["downtime_last_hour"],
                    round(store["downtime_last_day"], 2),
                    round(store["downtime_last_week"], 2),
                    store["timezone"],
                    store["now_s"]
                ])
        
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
