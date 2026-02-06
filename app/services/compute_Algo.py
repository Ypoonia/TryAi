import json
import csv
from datetime import datetime, timedelta, time
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from pathlib import Path
import pytz

logger = logging.getLogger(__name__)

class MinuteIndexReportService:
    def __init__(self, db: Session):
        self.db = db
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
#Generate csv
    def generate_store_report(self, report_id: str, max_stores: int = 100) -> Dict[str, Any]:
        try:
            logger.info(f"Starting minute-index report generation for {report_id}")
            max_utc = self._max_utc()
            logger.info(f"MAX_UTC: {max_utc}")
            stores = self._stores(max_stores)
            logger.info(f"Processing {len(stores)} stores")

            rows = []
            for s in stores:
                store_id = s["store_id"]
                tz_str = s["timezone_str"]
                logger.debug(f"Processing store {store_id} in timezone {tz_str}")
                try:
                    r = self._proc_store(store_id, tz_str, max_utc)
                    if r:
                        rows.append(r)
                except Exception as e:
                    logger.error(f"Error processing store {store_id}: {e}")
                    continue

            self._save_json(report_id, rows, max_utc)
            csv_path = self._save_csv(report_id, rows, max_utc)
            summary = self._summary(rows)
            logger.info(f"Minute-index report completed for {report_id}: {len(rows)} stores")

            return {
                "success": True,
                "report_id": report_id,
                "total_stores": len(rows),
                "file_path": str(csv_path),
                "summary": summary,
                "generated_at": datetime.utcnow().isoformat(),
                "max_utc": max_utc.isoformat(),
                "algorithm": "Carry-Forward (Seed-Before) Interval Sweep",
            }
        except Exception as e:
            logger.error(f"Error generating minute-index report {report_id}: {e}")
            return {"success": False, "error": str(e), "report_id": report_id}

    def _max_utc(self) -> datetime:
        q = text("SELECT MAX(timestamp_utc) FROM raw.store_status")
        r = self.db.execute(q).fetchone()
        v = r[0]
        if v is None:
            raise ValueError("raw.store_status is empty; no MAX(timestamp_utc)")
        if isinstance(v, str):
            v = v.replace(" UTC", "")
            dt = datetime.fromisoformat(v)
        else:
            dt = v
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt

    def _stores(self, limit: int) -> List[Dict[str, Any]]:
        q = text(
            """
            SELECT DISTINCT 
                s.store_id,
                COALESCE(t.timezone_str, 'America/Chicago') as timezone_str
            FROM raw.store_status s
            LEFT JOIN raw.timezones t ON s.store_id = t.store_id
            LIMIT :n
            """
        )
        rows = self.db.execute(q, {"n": limit}).fetchall()
        return [{"store_id": row[0], "timezone_str": row[1]} for row in rows]

    def _proc_store(self, store_id: str, tz_str: str, max_utc: datetime) -> Optional[Dict[str, Any]]:
        try:
            tz = pytz.timezone(tz_str or "America/Chicago")
        except Exception:
            logger.warning(f"Invalid timezone '{tz_str}' for store {store_id}; using UTC")
            tz = pytz.UTC
        now_local = self._floor_min(max_utc.astimezone(tz))
        logger.debug(f"Store {store_id}: NOW_s_local = {now_local} (local timezone: {tz_str})")

        H = (1, 61)
        D = (1, 1441)
        W = (1, 10081)

        polls = self._load_polls(store_id, tz, now_local)
        if not polls:
            logger.debug(f"Store {store_id}: No polls found, excluding")
            return None

        bh = self._build_bh(store_id, tz, now_local)
        B_H = sum(self._overlap(b, H) for b in bh)
        B_D = sum(self._overlap(b, D) for b in bh)
        B_W = sum(self._overlap(b, W) for b in bh)
        logger.debug(f"Store {store_id}: BH budgets H={B_H}, D={B_D}, W={B_W}")

        spans = self._spans(polls, W)
        U_H, U_D, U_W = self._sweep(bh, spans, H, D, W)

        U_H = self._clamp(U_H, 0, B_H)
        U_D = self._clamp(U_D, 0, B_D)
        U_W = self._clamp(U_W, 0, B_W)
        D_H = B_H - U_H
        D_D = B_D - U_D
        D_W = B_W - U_W

        assert abs((U_H + D_H) - B_H) < 1e-9
        assert abs((U_D + D_D) - B_D) < 1e-9
        assert abs((U_W + D_W) - B_W) < 1e-9

        return {
            "store_id": store_id,
            "uptime_last_hour": U_H,
            "uptime_last_day": U_D / 60.0,
            "uptime_last_week": U_W / 60.0,
            "downtime_last_hour": D_H,
            "downtime_last_day": D_D / 60.0,
            "downtime_last_week": D_W / 60.0,
            "timezone": tz_str,
            "now_s": now_local.isoformat(),
            "algorithm_details": {
                "total_polls": len(polls),
                "bh_intervals_count": len(bh),
                "status_spans_count": len(spans),
                "bh_budgets": {"H": B_H, "D": B_D, "W": B_W},
                "raw_uptimes": {"H": U_H, "D": U_D, "W": U_W},
            },
        }

    def _floor_min(self, dt: datetime) -> datetime:
        return dt.replace(second=0, microsecond=0)

    def _ceil_min(self, dt: datetime) -> datetime:
        if dt.second == 0 and dt.microsecond == 0:
            return dt
        return (dt + timedelta(minutes=1)).replace(second=0, microsecond=0)

    def _idx(self, dt_local: datetime, now_local: datetime) -> int:
        d = (now_local - dt_local).total_seconds() / 60.0
        return max(1, int(d) + 1)

    def _overlap(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        x1, x2 = a
        y1, y2 = b
        return max(0, min(x2, y2) - max(x1, y1))

    def _clamp(self, v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    def _tzloc(self, tz, dt):
        try:
            return tz.localize(dt, is_dst=None)
        except pytz.AmbiguousTimeError:
            return tz.localize(dt, is_dst=True)
        except pytz.NonExistentTimeError:
            return tz.localize(dt + timedelta(hours=1), is_dst=True)

    def _load_polls(self, store_id: str, tz: Optional[pytz.BaseTzInfo], now_local: datetime) -> List[Tuple[int, str]]:
        left = now_local - timedelta(minutes=10080 + 1440)
        left_utc = left.astimezone(pytz.UTC)
        q = text(
            """
            SELECT timestamp_utc, status
            FROM raw.store_status
            WHERE store_id = :sid
              AND timestamp_utc >= :left_utc
            ORDER BY timestamp_utc ASC
            """
        )
        rows = self.db.execute(q, {"sid": store_id, "left_utc": left_utc.strftime("%Y-%m-%d %H:%M:%S")}).fetchall()

        per_min = {}
        for t_utc, s in rows:
            if isinstance(t_utc, str):
                t_utc = t_utc.replace(" UTC", "")
                t = datetime.fromisoformat(t_utc)
                if t.tzinfo is None:
                    t = pytz.UTC.localize(t)
            else:
                t = t_utc
                if t.tzinfo is None:
                    t = pytz.UTC.localize(t)
            lt = t.astimezone(tz)
            lt = self._floor_min(lt)
            k = self._idx(lt, now_local)
            m = self._map_status(s)
            if m is None:
                continue
            if k not in per_min or t > per_min[k][0]:
                per_min[k] = (t, m)

        out = [(k, v[1]) for k, v in per_min.items()]
        out.sort(key=lambda x: x[0], reverse=True)
        logger.debug(f"Store {store_id}: Normalized {len(out)} polls")
        return out

    def _map_status(self, s: str) -> Optional[str]:
        v = s.lower().strip()
        if v == "active":
            return "active"
        if v == "inactive":
            return "inactive"
        return None

    def _build_bh(self, store_id: str, tz: Optional[pytz.BaseTzInfo], now_local: datetime) -> List[Tuple[int, int]]:
        q = text(
            """
            SELECT "dayOfWeek", start_time_local, end_time_local
            FROM raw.menu_hours
            WHERE store_id = :sid
            ORDER BY "dayOfWeek", start_time_local
            """
        )
        rows = self.db.execute(q, {"sid": store_id}).fetchall()
        if not rows:
            return [(1, 10081)]

        by_day: Dict[int, List[Tuple[str, str]]] = {}
        for d, s, e in rows:
            d = int(d)
            by_day.setdefault(d, []).append((s, e))

        ans: List[Tuple[int, int]] = []
        start_date = (now_local - timedelta(days=8)).date()
        end_date = (now_local + timedelta(days=1)).date()
        cur = start_date
        while cur <= end_date:
            if tz:
                midnight = self._tzloc(tz, datetime.combine(cur, time()))
            else:
                midnight = datetime.combine(cur, time())
            weekday = cur.weekday()
            if weekday in by_day:
                for s_str, e_str in by_day[weekday]:
                    s_t = self._parse_time(s_str)
                    e_t = self._parse_time(e_str)
                    s_dt = self._tzloc(tz, datetime.combine(cur, s_t)) if tz else datetime.combine(cur, s_t)
                    e_dt = self._tzloc(tz, datetime.combine(cur, e_t)) if tz else datetime.combine(cur, e_t)
                    if e_t <= s_t:
                        eod = self._tzloc(tz, datetime.combine(cur, time(23, 59, 59))) if tz else datetime.combine(
                            cur, time(23, 59, 59)
                        )
                        a = self._idx(self._floor_min(s_dt), now_local)
                        b = self._idx(self._ceil_min(eod), now_local)
                        if a > b:
                            ans.append((b, a))
                        nxt = cur + timedelta(days=1)
                        sod = self._tzloc(tz, datetime.combine(nxt, time())) if tz else datetime.combine(nxt, time())
                        e2 = self._tzloc(tz, datetime.combine(nxt, e_t)) if tz else datetime.combine(nxt, e_t)
                        a2 = self._idx(self._floor_min(sod), now_local)
                        b2 = self._idx(self._ceil_min(e2), now_local)
                        if a2 > b2:
                            ans.append((b2, a2))
                    else:
                        a = self._idx(self._floor_min(s_dt), now_local)
                        b = self._idx(self._ceil_min(e_dt), now_local)
                        if a > b:
                            ans.append((b, a))
            cur += timedelta(days=1)

        ans.sort()
        return self._merge(ans)

    def _parse_time(self, s: str) -> time:
        try:
            if len(s.split(":")) == 2:
                s += ":00"
            return time.fromisoformat(s)
        except Exception:
            try:
                p = s.split(":")
                h = int(p[0])
                m = int(p[1])
                sec = int(p[2]) if len(p) > 2 else 0
                return time(h, m, sec)
            except Exception:
                return time(0, 0, 0)

    def _merge(self, ivals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if not ivals:
            return []
        ivals.sort()
        out = [ivals[0]]
        for s, e in ivals[1:]:
            ls, le = out[-1]
            if s <= le:
                out[-1] = (ls, max(le, e))
            else:
                out.append((s, e))
        return out

    def _spans(self, polls: List[Tuple[int, str]], W: Tuple[int, int]) -> List[Tuple[int, int, str]]:
        if not polls:
            return [(W[0], W[1], "inactive")]
        start_k = W[1] - 1
        seed = "inactive"
        pre = [(k, s) for (k, s) in polls if k >= start_k]
        if pre:
            seed = min(pre, key=lambda x: x[0])[1]
        else:
            inside = [(k, s) for (k, s) in polls if W[0] <= k < W[1]]
            if inside:
                seed = min(inside, key=lambda x: x[0])[1]
        win = [(k, s) for (k, s) in polls if W[0] <= k < W[1]]
        if not win:
            return [(W[0], W[1], seed)]
        segs = []
        prev_k = start_k
        prev_s = seed
        for k, s in sorted(win, key=lambda x: -x[0]):
            a, b = sorted((k, prev_k))
            if a < b:
                segs.append((a, b, prev_s))
            prev_k, prev_s = k, s
        a, b = sorted((W[0], prev_k))
        if a < b:
            segs.append((a, b, prev_s))
        out: List[Tuple[int, int, str]] = []
        for s1, e1, st in sorted(segs):
            if out and out[-1][2] == st and out[-1][1] == s1:
                out[-1] = (out[-1][0], e1, st)
            else:
                out.append((s1, e1, st))
        return out

    def _sweep(
        self,
        bh: List[Tuple[int, int]],
        spans: List[Tuple[int, int, str]],
        H: Tuple[int, int],
        D: Tuple[int, int],
        W: Tuple[int, int],
    ) -> Tuple[float, float, float]:
        U_H = U_D = U_W = 0.0
        i = j = 0
        while i < len(bh) and j < len(spans):
            bs, be = bh[i]
            ss, se, st = spans[j]
            s = max(bs, ss)
            e = min(be, se)
            if s < e:
                iv = (s, e)
                oh = self._overlap(iv, H)
                od = self._overlap(iv, D)
                ow = self._overlap(iv, W)
                if st == "active":
                    U_H += oh
                    U_D += od
                    U_W += ow
            if be <= se:
                i += 1
            if se <= be:
                j += 1
        return U_H, U_D, U_W

    def _save_json(self, report_id: str, rows: List[Dict], max_utc: datetime) -> Path:
        path = self.reports_dir / f"{report_id}.json"
        payload = {
            "report_metadata": {
                "report_id": report_id,
                "generated_at": datetime.utcnow().isoformat(),
                "total_stores": len(rows),
                "max_utc": max_utc.isoformat(),
                "algorithm": "Carry-Forward (Seed-Before) Interval Sweep",
                "bands": {"H": "[1, 61)", "D": "[1, 1441)", "W": "[1, 10081)"},
                "schema": [
                    "store_id",
                    "uptime_last_hour (minutes)",
                    "uptime_last_day (hours)",
                    "uptime_last_week (hours)",
                    "downtime_last_hour (minutes)",
                    "downtime_last_day (hours)",
                    "downtime_last_week (hours)",
                ],
            },
            "report_data": rows,
            "algorithm_details": {
                "description": "Carry-forward logic with seed-before interpolation",
                "features": [
                    "Local minute index",
                    "Timezone conversion per store",
                    "Business hours as index intervals",
                    "Carry-forward interpolation",
                    "Two-pointer intersection",
                    "Uptime+Downtime=Coverage invariants",
                ],
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info(f"Minute-index report saved to {path}")
        return path

    def _save_csv(self, report_id: str, rows: List[Dict], max_utc: datetime) -> Path:
        path = self.reports_dir / f"{report_id}.csv"
        header = [
            "store_id",
            "uptime_last_hour (minutes)",
            "uptime_last_day (hours)",
            "uptime_last_week (hours)",
            "downtime_last_hour (minutes)",
            "downtime_last_day (hours)",
            "downtime_last_week (hours)",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in rows:
                w.writerow(
                    [
                        r["store_id"],
                        r["uptime_last_hour"],
                        round(r["uptime_last_day"], 2),
                        round(r["uptime_last_week"], 2),
                        r["downtime_last_hour"],
                        round(r["downtime_last_day"], 2),
                        round(r["downtime_last_week"], 2),
                    ]
                )
        logger.info(f"Minute-index report saved to {path}")
        return path

    def _summary(self, rows: List[Dict]) -> Dict[str, Any]:
        if not rows:
            return {"message": "No data to summarize"}
        n = len(rows)
        avg_u_h = sum(r["uptime_last_hour"] for r in rows) / n
        avg_u_d = sum(r["uptime_last_day"] for r in rows) / n
        avg_u_w = sum(r["uptime_last_week"] for r in rows) / n
        avg_d_h = sum(r["downtime_last_hour"] for r in rows) / n
        avg_d_d = sum(r["downtime_last_day"] for r in rows) / n
        avg_d_w = sum(r["downtime_last_week"] for r in rows) / n
        act_h = sum(1 for r in rows if r["uptime_last_hour"] > r["downtime_last_hour"])
        act_d = sum(1 for r in rows if r["uptime_last_day"] > r["downtime_last_day"])
        act_w = sum(1 for r in rows if r["uptime_last_week"] > r["downtime_last_week"])
        total_polls = sum(r["algorithm_details"]["total_polls"] for r in rows)
        avg_polls = total_polls / n if n else 0
        return {
            "total_stores": n,
            "algorithm": "Carry-Forward (Seed-Before) Interval Sweep",
            "averages": {
                "uptime_last_hour_minutes": round(avg_u_h, 2),
                "uptime_last_day_hours": round(avg_u_d, 2),
                "uptime_last_week_hours": round(avg_u_w, 2),
                "downtime_last_hour_minutes": round(avg_d_h, 2),
                "downtime_last_day_hours": round(avg_d_d, 2),
                "downtime_last_week_hours": round(avg_d_w, 2),
            },
            "active_stores": {
                "last_hour": f"{act_h}/{n} ({100*act_h/n:.1f}%)",
                "last_day": f"{act_d}/{n} ({100*act_d/n:.1f}%)",
                "last_week": f"{act_w}/{n} ({100*act_w/n:.1f}%)",
            },
            "efficiency": {
                "total_polls_processed": total_polls,
                "avg_polls_per_store": round(avg_polls, 1),
                "minute_level_precision": True,
                "timezone_aware": True,
                "carry_forward_seed_before": True,
            },
        }
