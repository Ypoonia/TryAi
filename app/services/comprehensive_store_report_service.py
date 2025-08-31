#!/usr/bin/env python3
"""
Comprehensive Store Report Service
Processes EVERY unique store ID with proper data normalization

Features:
1. Find all unique store IDs from database
2. Normalize missing data:
   - Missing business hours → 24/7 operation
   - Missing timezone → America/Chicago
3. Calculate uptime/downtime for every store
4. Use latest data from database
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from pathlib import Path
import pytz
from collections import defaultdict
import math

from app.core.config import settings

logger = logging.getLogger(__name__)

class ComprehensiveStoreReportService:
    """
    Enhanced Store Report Service for ALL stores with data normalization
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
    
    def generate_comprehensive_report(self, report_id: str) -> Dict[str, Any]:
        """
        Generate comprehensive report for ALL unique store IDs
        """
        try:
            logger.info(f"Starting comprehensive store report for {report_id}")
            
            # Step 0: Get MAX_UTC and setup
            max_utc = self._get_max_timestamp_utc()
            logger.info(f"MAX_UTC: {max_utc}")
            
            # Step 1: Find ALL unique store IDs
            all_store_ids = self._get_all_unique_store_ids()
            logger.info(f"Found {len(all_store_ids)} unique store IDs")
            
            # Step 2: Process each store with normalization
            report_data = []
            processed_count = 0
            
            for store_id in all_store_ids:
                try:
                    # Fetch & normalize only for THIS store
                    normalized_store = self._normalize_store_data(store_id)
                    
                    # Calculate metrics using minute-index algorithm
                    store_metrics = self._process_store_with_minute_index(
                        normalized_store, max_utc
                    )
                    
                    if store_metrics:
                        report_data.append(store_metrics)
                        processed_count += 1
                        
                        if processed_count % 100 == 0:
                            logger.info(f"Processed {processed_count} stores...")
                
                except Exception as e:
                    logger.error(f"Error processing store {store_id}: {e}")
                    continue
            
            # Step 3: Save comprehensive report
            report_file_path = self._save_comprehensive_report(
                report_id, report_data, max_utc, all_store_ids
            )
            
            # Step 4: Generate summary
            summary = self._generate_comprehensive_summary(report_data, all_store_ids)
            
            logger.info(f"Comprehensive report completed: {len(report_data)}/{len(all_store_ids)} stores processed")
            
            return {
                "success": True,
                "report_id": report_id,
                "total_unique_stores": len(all_store_ids),
                "successfully_processed": len(report_data),
                "file_path": str(report_file_path),
                "summary": summary,
                "generated_at": datetime.utcnow().isoformat(),
                "max_utc": max_utc.isoformat(),
                "algorithm": "Comprehensive Minute-Index with Data Normalization"
            }
            
        except Exception as e:
            logger.error(f"Error generating comprehensive report {report_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "report_id": report_id
            }
    
    def _get_max_timestamp_utc(self) -> datetime:
        """Get MAX(timestamp_utc) from raw.store_status"""
        
        query = text("SELECT MAX(timestamp_utc) FROM raw.store_status")
        result = self.db.execute(query).fetchone()
        
        max_utc = result[0]
        if isinstance(max_utc, str):
            max_utc = datetime.fromisoformat(max_utc.replace(' UTC', ''))
        if max_utc.tzinfo is None:
            max_utc = pytz.UTC.localize(max_utc)
        
        return max_utc
    
    def _get_all_unique_store_ids(self) -> Set[str]:
        """
        Get ALL unique store IDs from all relevant tables
        """
        
        # Get store IDs from store_status (main source)
        query1 = text("SELECT DISTINCT store_id FROM raw.store_status")
        status_stores = set(row[0] for row in self.db.execute(query1).fetchall())
        
        # Get store IDs from timezones  
        query2 = text("SELECT DISTINCT store_id FROM raw.timezones")
        timezone_stores = set(row[0] for row in self.db.execute(query2).fetchall())
        
        # Get store IDs from menu_hours
        query3 = text("SELECT DISTINCT store_id FROM raw.menu_hours")
        menu_stores = set(row[0] for row in self.db.execute(query3).fetchall())
        
        # Union of all store IDs
        all_stores = status_stores | timezone_stores | menu_stores
        
        logger.info(f"Store IDs found: status={len(status_stores)}, timezones={len(timezone_stores)}, menu_hours={len(menu_stores)}")
        logger.info(f"Total unique stores: {len(all_stores)}")
        
        return all_stores
    
    def _get_timezone_for_store(self, store_id: str) -> Tuple[str, bool]:
        """Return (tz_str, defaulted) for a store."""
        query = text("""SELECT timezone_str FROM raw.timezones
                    WHERE store_id = :sid LIMIT 1""")
        row = self.db.execute(query, {"sid": store_id}).fetchone()
        if row and row[0]:
            return row[0], False
        return "America/Chicago", True

    def _get_menu_hours_for_store(self, store_id: str) -> Tuple[Dict[int, List[Tuple[str, str]]], bool]:
        """
        Return (by_day, defaulted). by_day: {int_dow: [(start,end), ...]}
        """
        query = text("""
            SELECT "dayOfWeek", start_time_local, end_time_local
            FROM raw.menu_hours
            WHERE store_id = :sid
            ORDER BY "dayOfWeek", start_time_local
        """)
        rows = self.db.execute(query, {"sid": store_id}).fetchall()

        if not rows:
            # 24/7 default for each day
            return ({d: [("00:00:00", "23:59:59")] for d in range(7)}, True)

        by_day = defaultdict(list)
        for dow, start, end in rows:
            by_day[int(dow)].append((start, end))
        return (dict(by_day), False)
    
    def _normalize_store_data(self, store_id: str) -> Dict[str, Any]:
        """
        Normalize store data with defaults for missing information
        """
        tz_str, tz_defaulted = self._get_timezone_for_store(store_id)
        bh_by_day, bh_defaulted = self._get_menu_hours_for_store(store_id)

        return {
            "store_id": store_id,
            "timezone_str": tz_str,
            "business_hours": bh_by_day,  # {dow: [(start, end), ...]}
            "normalized": {
                "timezone_defaulted": tz_defaulted,
                "business_hours_defaulted": bh_defaulted,
            },
        }
    
    def _process_store_with_minute_index(self, store_data: Dict[str, Any], max_utc: datetime) -> Optional[Dict[str, Any]]:
        """
        Process a single store using the minute index algorithm
        """
        
        store_id = store_data["store_id"]
        tz_str = store_data["timezone_str"]
        business_hours = store_data["business_hours"]
        
        # Define bands
        H = (1, 61)      # Hour
        D = (1, 1441)    # Day
        W = (1, 10081)   # Week
        
        # Setup timezone object
        try:
            store_tz = pytz.timezone(tz_str)
        except Exception as e:
            logger.warning(f"Invalid timezone '{tz_str}' for store {store_id}, using UTC")
            store_tz = pytz.UTC
        
        # Setup timezone and NOW_s in local timezone
        now_s_local = self._floor_minute(max_utc.astimezone(store_tz))
        
        # Load & normalize polls (using local timezone)
        polls_normalized = self._load_and_normalize_polls(store_id, store_tz, now_s_local)
        
        # SKIP if store has no polls (per business rule)
        if not polls_normalized:
            return None
        
        # Build BH intervals (using local timezone)
        bh_intervals = self._build_bh_intervals_from_data(business_hours, store_tz, now_s_local)
        
        # Calculate BH budgets
        B_H = sum(self._overlap_len(interval, H) for interval in bh_intervals)
        B_D = sum(self._overlap_len(interval, D) for interval in bh_intervals)
        B_W = sum(self._overlap_len(interval, W) for interval in bh_intervals)
        
        # Build status spans with pure carry-forward logic
        status_spans = self._build_status_spans_carry_forward(polls_normalized, W)
        
        # Two-pointer sweep
        U_H, U_D, U_W = self._two_pointer_sweep(bh_intervals, status_spans, H, D, W)
        
        # Clamp and validate
        U_H = self._clamp(U_H, 0, B_H)
        U_D = self._clamp(U_D, 0, B_D)
        U_W = self._clamp(U_W, 0, B_W)
        
        D_H = B_H - U_H
        D_D = B_D - U_D
        D_W = B_W - U_W
        
        # Assert invariants (optional but recommended)
        eps = 1e-9
        assert abs((U_H + (B_H - U_H)) - B_H) < eps, f"Hour invariant failed: U_H={U_H}, B_H={B_H}"
        assert abs((U_D + (B_D - U_D)) - B_D) < eps, f"Day invariant failed: U_D={U_D}, B_D={B_D}"
        assert abs((U_W + (B_W - U_W)) - B_W) < eps, f"Week invariant failed: U_W={U_W}, B_W={B_W}"
        
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
            "normalization": store_data["normalized"],
            "algorithm_details": {
                "total_polls": len(polls_normalized),
                "bh_intervals_count": len(bh_intervals),
                "status_spans_count": len(status_spans),
                "bh_budgets": {"H": B_H, "D": B_D, "W": B_W},
                "raw_uptimes": {"H": U_H, "D": U_D, "W": U_W}
            }
        }
    
    # Helper methods (reuse from minute_index_report_service.py)
    
    def _floor_minute(self, dt: datetime) -> datetime:
        return dt.replace(second=0, microsecond=0)
    
    def _ceil_minute(self, dt: datetime) -> datetime:
        """Ceiling to next minute boundary (for inclusive BH end times)"""
        if dt.second == 0 and dt.microsecond == 0:
            return dt
        return (dt + timedelta(minutes=1)).replace(second=0, microsecond=0)
    
    def _minute_index(self, dt_local: datetime, now_s_local: datetime) -> int:
        """Map local datetime dt_local (floored to minute) to index k
        Both dt_local and now_s_local MUST be tz-aware in the SAME timezone"""
        delta_minutes = (now_s_local - dt_local).total_seconds() / 60.0
        # Fix off-by-one: use int(...) + 1 to avoid collapsing adjacent minute boundaries
        # This ensures 1-hour BH (11:00-12:00) maps to indices (1,61) = 60 minutes
        return max(1, int(delta_minutes) + 1)
    
    def _overlap_len(self, interval1: Tuple[int, int], interval2: Tuple[int, int]) -> int:
        a, b = interval1
        x, y = interval2
        return max(0, min(b, y) - max(a, x))
    
    def _clamp(self, value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))
    
    def _localize_safe(self, tz: pytz.BaseTzInfo, dt: datetime) -> datetime:
        """DST-safe localization for business hours"""
        try:
            return tz.localize(dt, is_dst=None)  # raise on ambiguous / nonexistent
        except pytz.AmbiguousTimeError:
            return tz.localize(dt, is_dst=True)   # choose one (or parametrize)
        except pytz.NonExistentTimeError:
            return tz.localize(dt + timedelta(hours=1), is_dst=True)  # nudge forward
    
    def _load_and_normalize_polls(self, store_id: str, store_tz: Optional[pytz.BaseTzInfo], now_s_local: datetime) -> List[Tuple[int, str]]:
        """Load and normalize polls for the store"""
        
        left_buf_minutes = 1440
        left_dt_local = now_s_local - timedelta(minutes=10080 + left_buf_minutes)  # tz-aware
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
        
        minute_polls = {}
        
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

            # Convert to local timezone (both timezone-aware in same tz)
            timestamp_local = timestamp_utc.astimezone(store_tz)
            dt_local_floored = self._floor_minute(timestamp_local)
            minute_index = self._minute_index(dt_local_floored, now_s_local)
            
            norm_status = self._map_to_active_inactive(status)
            if norm_status is None:
                continue
            
            if minute_index not in minute_polls or timestamp_utc > minute_polls[minute_index][0]:
                minute_polls[minute_index] = (timestamp_utc, norm_status)
        
        polls_normalized = []
        for minute_index, (_, status) in minute_polls.items():
            polls_normalized.append((minute_index, status))
        
        # Keep ASC order here for seed selection
        polls_normalized.sort(key=lambda x: x[0])  # ascending by index
        return polls_normalized
    
    def _map_to_active_inactive(self, status: str) -> Optional[str]:
        status_lower = status.lower().strip()
        if status_lower == 'active':
            return 'active'
        elif status_lower == 'inactive':
            return 'inactive'
        else:
            return None
    
    def _build_bh_intervals_from_data(self, business_hours: Dict[int, List[Tuple[str, str]]], 
                                    store_tz: Optional[pytz.BaseTzInfo], now_s_local: datetime) -> List[Tuple[int, int]]:
        """Build business hours intervals from normalized data"""
        
        bh_intervals = []
        
        # Iterate local midnights, not .date() alone
        day0 = now_s_local.replace(hour=0, minute=0, second=0, microsecond=0)
        cursor = (day0 - timedelta(days=8))
        endcap = (day0 + timedelta(days=1))
        
        while cursor <= endcap:
            dow = cursor.weekday()
            
            if dow in business_hours:
                for start_str, end_str in business_hours[dow]:
                    s = self._parse_time_str(start_str)
                    e = self._parse_time_str(end_str)

                    # Create naive datetimes first, then localize safely
                    start_dt_naive = cursor.replace(hour=s.hour, minute=s.minute, second=s.second, microsecond=0, tzinfo=None)
                    end_dt_naive = cursor.replace(hour=e.hour, minute=e.minute, second=e.second, microsecond=0, tzinfo=None)

                    segs = []
                    if end_dt_naive <= start_dt_naive:  # overnight
                        midnight_next_naive = cursor.replace(tzinfo=None) + timedelta(days=1)
                        segs = [(start_dt_naive, midnight_next_naive),  # [start, next 00:00)
                                (midnight_next_naive.replace(hour=0, minute=0, second=0, microsecond=0), 
                                 end_dt_naive + timedelta(days=1))]
                    else:
                        segs = [(start_dt_naive, end_dt_naive)]  # [start, end)

                    for a_naive, b_naive in segs:
                        # Use DST-safe localization
                        a = self._localize_safe(store_tz, a_naive)
                        b = self._localize_safe(store_tz, b_naive)
                        
                        # Fix: Use _ceil_minute for end to include full last minute
                        # BH of 00:00:00 → 23:59:59 becomes [00:00, 24:00) = 1440 minutes
                        k_end   = self._minute_index(self._ceil_minute(b), now_s_local)   # end (exclusive)
                        k_start = self._minute_index(self._floor_minute(a), now_s_local)  # start (inclusive)
                        a_idx, b_idx = sorted((k_end, k_start))
                        if 1 <= a_idx < b_idx <= 10081:
                            bh_intervals.append((a_idx, b_idx))
            
            cursor += timedelta(days=1)
        
        return self._merge_sorted_intervals(bh_intervals)
    
    def _parse_time_str(self, time_str: str) -> datetime.time:
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
        if not windows:
            return []
        windows.sort(key=lambda x: x[0])
        merged = [windows[0]]
        for start, end in windows[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged
    
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
        
        # find the minimal k >= start_k (closest to start_k)
        candidates = [(k, s) for (k, s) in polls_idx if k >= start_k]
        if candidates:
            k_min, s_min = min(candidates, key=lambda x: x[0])  # closest to start_k
            seed_status = s_min
        else:
            # No pre-window poll found, check if we have in-window polls
            in_window_polls = [(k, s) for (k, s) in polls_idx if W[0] <= k < W[1]]
            if in_window_polls:
                # Use the earliest in-window status rather than hard 'inactive'
                first_in_k, first_in_s = min(in_window_polls, key=lambda x: x[0])
                seed_status = first_in_s
                
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
        if not intervals:
            return []
        intervals.sort()
        merged = [intervals[0]]
        for start, end in intervals[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged
    
    def _two_pointer_sweep(self, bh_intervals: List[Tuple[int, int]], 
                          status_spans: List[Tuple[int, int, str]],
                          H: Tuple[int, int], D: Tuple[int, int], W: Tuple[int, int]) -> Tuple[float, float, float]:
        """Two-pointer sweep over BH × status spans"""
        
        U_H = U_D = U_W = 0.0
        
        i = j = 0
        while i < len(bh_intervals) and j < len(status_spans):
            bh_start, bh_end = bh_intervals[i]
            span_start, span_end, status = status_spans[j]
            
            overlap_start = max(bh_start, span_start)
            overlap_end = min(bh_end, span_end)
            
            if overlap_start < overlap_end:
                overlap_interval = (overlap_start, overlap_end)
                oh = self._overlap_len(overlap_interval, H)
                od = self._overlap_len(overlap_interval, D)
                ow = self._overlap_len(overlap_interval, W)
                
                if status == 'active':
                    U_H += oh
                    U_D += od
                    U_W += ow
            
            if bh_end <= span_end:
                i += 1
            if span_end <= bh_end:
                j += 1
        
        return U_H, U_D, U_W
    
    def _save_comprehensive_report(self, report_id: str, report_data: List[Dict], 
                                 max_utc: datetime, all_store_ids: Set[str]) -> Path:
        """Save comprehensive report with all store data"""
        
        report_file = self.reports_dir / f"{report_id}_comprehensive.json"
        
        # Sort report data by store_id for easier validation
        report_data.sort(key=lambda x: x["store_id"])
        
        # Create processed store IDs set
        processed_store_ids = {store["store_id"] for store in report_data}
        failed_store_ids = all_store_ids - processed_store_ids
        
        full_report = {
            "report_metadata": {
                "report_id": report_id,
                "generated_at": datetime.utcnow().isoformat(),
                "total_unique_stores": len(all_store_ids),
                "successfully_processed": len(report_data),
                "failed_stores": len(failed_store_ids),
                "max_utc": max_utc.isoformat(),
                "algorithm": "Comprehensive Minute-Index with Data Normalization",
                "data_normalization": {
                    "default_timezone": "America/Chicago",
                    "default_business_hours": "24/7 (00:00:00 - 23:59:59)",
                    "applied_for_missing_data": True
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
            "failed_store_ids": sorted(list(failed_store_ids)),
            "normalization_summary": {
                "stores_with_default_timezone": sum(1 for store in report_data if store["normalization"]["timezone_defaulted"]),
                "stores_with_default_business_hours": sum(1 for store in report_data if store["normalization"]["business_hours_defaulted"])
            }
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(full_report, f, indent=2, default=str)
        
        logger.info(f"Comprehensive report saved to {report_file}")
        return report_file
    
    def _generate_comprehensive_summary(self, report_data: List[Dict], all_store_ids: Set[str]) -> Dict[str, Any]:
        """Generate comprehensive summary statistics"""
        
        if not report_data:
            return {"message": "No data to summarize"}
        
        total_stores = len(all_store_ids)
        processed_stores = len(report_data)
        
        # Calculate averages
        avg_uptime_hour = sum(store["uptime_last_hour"] for store in report_data) / processed_stores
        avg_uptime_day = sum(store["uptime_last_day"] for store in report_data) / processed_stores
        avg_uptime_week = sum(store["uptime_last_week"] for store in report_data) / processed_stores
        
        # Normalization stats
        timezone_defaulted = sum(1 for store in report_data if store["normalization"]["timezone_defaulted"])
        bh_defaulted = sum(1 for store in report_data if store["normalization"]["business_hours_defaulted"])
        
        # Active store counts
        active_hour = sum(1 for store in report_data if store["uptime_last_hour"] > store["downtime_last_hour"])
        active_day = sum(1 for store in report_data if store["uptime_last_day"] > store["downtime_last_day"])
        active_week = sum(1 for store in report_data if store["uptime_last_week"] > store["downtime_last_week"])
        
        return {
            "total_unique_stores": total_stores,
            "successfully_processed": processed_stores,
            "processing_rate": f"{100 * processed_stores / total_stores:.1f}%",
            "data_normalization": {
                "stores_with_default_timezone": f"{timezone_defaulted}/{processed_stores} ({100*timezone_defaulted/processed_stores:.1f}%)",
                "stores_with_default_business_hours": f"{bh_defaulted}/{processed_stores} ({100*bh_defaulted/processed_stores:.1f}%)"
            },
            "averages": {
                "uptime_last_hour_minutes": round(avg_uptime_hour, 2),
                "uptime_last_day_hours": round(avg_uptime_day, 2),
                "uptime_last_week_hours": round(avg_uptime_week, 2)
            },
            "active_stores": {
                "last_hour": f"{active_hour}/{processed_stores} ({100*active_hour/processed_stores:.1f}%)",
                "last_day": f"{active_day}/{processed_stores} ({100*active_day/processed_stores:.1f}%)",
                "last_week": f"{active_week}/{processed_stores} ({100*active_week/processed_stores:.1f}%)"
            },
            "algorithm": "Comprehensive Minute-Index with Data Normalization"
        }
