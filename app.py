#!/usr/bin/env python3
"""Tiny walking tracker API.

Run with:
    python3 app.py
"""

from __future__ import annotations

import json
import mimetypes
import os
import sqlite3
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
STATIC_DIR = APP_DIR / "static"
INDEX_PATH = APP_DIR / "static" / "index.html"
DB_PATH = Path(os.environ.get("WALK_TRACKER_DB", DATA_DIR / "walk_records.sqlite3"))
DEFAULT_USER_ID = "default"
DEFAULT_STRIDE_METERS = 0.7
DEFAULT_ACTIVITY_TYPE = "walk"
ACTIVITY_TYPES = {"walk", "run", "rope", "swim"}
ACTIVITY_METS = {
    "walk": 3.5,
    "run": 8.3,
    "rope": 10.0,
    "swim": 7.0,
}
DEFAULT_WEIGHT_KG = 60
DEFAULT_HOST = os.environ.get("HOST", "0.0.0.0")
DEFAULT_PORT = int(os.environ.get("PORT", "8000"))


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def today_string() -> str:
    return date.today().isoformat()


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format") from exc


def to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def normalize_steps(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        steps = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("steps must be an integer") from exc
    if steps < 0:
        raise ValueError("steps cannot be negative")
    return steps


def normalize_stride(value: Any) -> float:
    if value is None or value == "":
        return DEFAULT_STRIDE_METERS
    try:
        stride = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("stride_meters must be a number") from exc
    if stride <= 0:
        raise ValueError("stride_meters must be greater than 0")
    return stride


def normalize_activity_type(value: Any) -> str:
    if value is None or value == "":
        return DEFAULT_ACTIVITY_TYPE
    activity_type = str(value).strip().lower()
    if activity_type not in ACTIVITY_TYPES:
        allowed = ", ".join(sorted(ACTIVITY_TYPES))
        raise ValueError(f"activity_type must be one of: {allowed}")
    return activity_type


def normalize_minutes(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        minutes = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("duration_minutes must be an integer") from exc
    if minutes < 0:
        raise ValueError("duration_minutes cannot be negative")
    return minutes


def normalize_calories(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        calories = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("calories must be an integer") from exc
    if calories < 0:
        raise ValueError("calories cannot be negative")
    return calories


def distance_km_for_steps(steps: int, stride_meters: float) -> float:
    return round((steps * stride_meters) / 1000, 2)


def estimate_calories(activity_type: str, duration_minutes: int) -> int:
    if duration_minutes <= 0:
        return 0
    met = ACTIVITY_METS.get(activity_type, ACTIVITY_METS[DEFAULT_ACTIVITY_TYPE])
    return round(met * 3.5 * DEFAULT_WEIGHT_KG / 200 * duration_minutes)


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS walk_records (
                user_id TEXT NOT NULL,
                date TEXT NOT NULL,
                activity_type TEXT NOT NULL DEFAULT 'walk',
                checked_in INTEGER NOT NULL DEFAULT 0,
                steps INTEGER NOT NULL DEFAULT 0,
                duration_minutes INTEGER NOT NULL DEFAULT 0,
                stride_meters REAL NOT NULL DEFAULT 0.7,
                distance_km REAL NOT NULL DEFAULT 0,
                calories INTEGER NOT NULL DEFAULT 0,
                note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, date)
            )
            """
        )
        ensure_column(conn, "activity_type", "activity_type TEXT NOT NULL DEFAULT 'walk'")
        ensure_column(conn, "duration_minutes", "duration_minutes INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "calories", "calories INTEGER NOT NULL DEFAULT 0")


def ensure_column(conn: sqlite3.Connection, column_name: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(walk_records)")}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE walk_records ADD COLUMN {definition}")


def row_to_record(row: sqlite3.Row | None, target_date: str) -> dict[str, Any]:
    if row is None:
        return {
            "date": target_date,
            "activity_type": DEFAULT_ACTIVITY_TYPE,
            "checked_in": False,
            "steps": 0,
            "duration_minutes": 0,
            "stride_meters": DEFAULT_STRIDE_METERS,
            "distance_km": 0,
            "calories": 0,
            "note": None,
            "created_at": None,
            "updated_at": None,
        }

    return {
        "date": row["date"],
        "activity_type": row["activity_type"],
        "checked_in": bool(row["checked_in"]),
        "steps": row["steps"],
        "duration_minutes": row["duration_minutes"],
        "stride_meters": row["stride_meters"],
        "distance_km": row["distance_km"],
        "calories": row["calories"],
        "note": row["note"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_record(user_id: str, target_date: str) -> dict[str, Any]:
    parse_date(target_date)
    with connect_db() as conn:
        row = conn.execute(
            "SELECT * FROM walk_records WHERE user_id = ? AND date = ?",
            (user_id, target_date),
        ).fetchone()
    return row_to_record(row, target_date)


def upsert_record(
    *,
    user_id: str,
    target_date: str,
    checked_in: bool,
    steps: int,
    stride_meters: float,
    note: str | None,
    activity_type: str = DEFAULT_ACTIVITY_TYPE,
    duration_minutes: int = 0,
    calories: int | None = None,
) -> dict[str, Any]:
    parse_date(target_date)
    activity_type = normalize_activity_type(activity_type)
    distance_km = distance_km_for_steps(steps, stride_meters)
    calories = calories if calories is not None else estimate_calories(activity_type, duration_minutes)
    now = utc_now_iso()
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO walk_records (
                user_id, date, activity_type, checked_in, steps, duration_minutes,
                stride_meters, distance_km, calories, note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                activity_type = excluded.activity_type,
                checked_in = excluded.checked_in,
                steps = excluded.steps,
                duration_minutes = excluded.duration_minutes,
                stride_meters = excluded.stride_meters,
                distance_km = excluded.distance_km,
                calories = excluded.calories,
                note = excluded.note,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                target_date,
                activity_type,
                int(checked_in),
                steps,
                duration_minutes,
                stride_meters,
                distance_km,
                calories,
                note,
                now,
                now,
            ),
        )
    return get_record(user_id, target_date)


def delete_record(user_id: str, target_date: str) -> bool:
    parse_date(target_date)
    with connect_db() as conn:
        cursor = conn.execute(
            "DELETE FROM walk_records WHERE user_id = ? AND date = ?",
            (user_id, target_date),
        )
    return cursor.rowcount > 0


def records_for_days(user_id: str, days: int) -> list[dict[str, Any]]:
    if days <= 0 or days > 366:
        raise ValueError("days must be between 1 and 366")

    end = date.today()
    start = end - timedelta(days=days - 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(days)]

    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM walk_records
            WHERE user_id = ? AND date BETWEEN ? AND ?
            ORDER BY date ASC
            """,
            (user_id, dates[0], dates[-1]),
        ).fetchall()

    rows_by_date = {row["date"]: row for row in rows}
    return [row_to_record(rows_by_date.get(item), item) for item in dates]


def stats_for_days(user_id: str, days: int) -> dict[str, Any]:
    records = records_for_days(user_id, days)
    total_steps = sum(item["steps"] for item in records)
    total_distance_km = round(sum(item["distance_km"] for item in records), 2)
    total_duration_minutes = sum(item["duration_minutes"] for item in records)
    total_calories = sum(item["calories"] for item in records)
    checked_in_days = sum(1 for item in records if item["checked_in"])
    average_steps = round(total_steps / days) if days else 0
    activity_counts: dict[str, int] = {}
    for item in records:
        if item["checked_in"]:
            activity_type = item["activity_type"]
            activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1

    streak_days = 0
    for item in reversed(records):
        if item["checked_in"]:
            streak_days += 1
        else:
            break

    return {
        "days": days,
        "checked_in_days": checked_in_days,
        "missed_days": days - checked_in_days,
        "total_steps": total_steps,
        "total_distance_km": total_distance_km,
        "total_duration_minutes": total_duration_minutes,
        "total_calories": total_calories,
        "average_steps": average_steps,
        "streak_days": streak_days,
        "activity_counts": activity_counts,
        "records": records,
    }


class WalkTrackerHandler(BaseHTTPRequestHandler):
    server_version = "WalkTrackerAPI/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            user_id = query.get("user_id", [DEFAULT_USER_ID])[0] or DEFAULT_USER_ID

            if path == "/":
                self.send_html(INDEX_PATH.read_text(encoding="utf-8"))
                return

            if path == "/manifest.webmanifest":
                self.send_file(STATIC_DIR / "manifest.webmanifest")
                return

            if path == "/service-worker.js":
                self.send_file(STATIC_DIR / "service-worker.js")
                return

            if path.startswith("/icons/"):
                self.send_static_file(path)
                return

            if path.startswith("/assets/"):
                self.send_static_file(path)
                return

            if path == "/health":
                self.send_json({"ok": True, "service": "walk-tracker-backend"})
                return

            if path == "/records/today":
                self.send_json({"record": get_record(user_id, today_string())})
                return

            if path == "/records":
                days = int(query.get("days", ["7"])[0])
                self.send_json({"records": records_for_days(user_id, days)})
                return

            if path == "/stats":
                days = int(query.get("days", ["7"])[0])
                self.send_json(stats_for_days(user_id, days))
                return

            if path.startswith("/records/"):
                target_date = path.split("/", 2)[2]
                self.send_json({"record": get_record(user_id, target_date)})
                return

            self.send_error_json(404, "not found")
        except ValueError as exc:
            self.send_error_json(400, str(exc))
        except Exception as exc:  # pragma: no cover - last line of defense for API use
            self.send_error_json(500, f"internal server error: {exc}")

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path != "/records/check-in":
                self.send_error_json(404, "not found")
                return

            payload = self.read_json_body()
            user_id = str(payload.get("user_id") or DEFAULT_USER_ID)
            target_date = str(payload.get("date") or today_string())
            activity_type = normalize_activity_type(payload.get("activity_type"))
            steps = normalize_steps(payload.get("steps"))
            duration_minutes = normalize_minutes(payload.get("duration_minutes"))
            stride_meters = normalize_stride(payload.get("stride_meters"))
            calories = normalize_calories(payload.get("calories"))
            note = payload.get("note")
            checked_in = to_bool(payload.get("checked_in"), default=True)

            record = upsert_record(
                user_id=user_id,
                target_date=target_date,
                checked_in=checked_in,
                steps=steps,
                stride_meters=stride_meters,
                note=note,
                activity_type=activity_type,
                duration_minutes=duration_minutes,
                calories=calories,
            )
            self.send_json({"record": record}, status=201)
        except ValueError as exc:
            self.send_error_json(400, str(exc))
        except Exception as exc:  # pragma: no cover
            self.send_error_json(500, f"internal server error: {exc}")

    def do_PUT(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if not path.startswith("/records/"):
                self.send_error_json(404, "not found")
                return

            payload = self.read_json_body()
            user_id = str(payload.get("user_id") or DEFAULT_USER_ID)
            target_date = path.split("/", 2)[2]
            existing = get_record(user_id, target_date)

            activity_type = normalize_activity_type(
                payload.get("activity_type", existing["activity_type"])
            )
            steps = normalize_steps(payload.get("steps", existing["steps"]))
            duration_minutes = normalize_minutes(
                payload.get("duration_minutes", existing["duration_minutes"])
            )
            stride_meters = normalize_stride(
                payload.get("stride_meters", existing["stride_meters"])
            )
            calories = normalize_calories(payload.get("calories", existing["calories"]))
            checked_in = to_bool(payload.get("checked_in"), existing["checked_in"])
            note = payload.get("note", existing["note"])

            record = upsert_record(
                user_id=user_id,
                target_date=target_date,
                checked_in=checked_in,
                steps=steps,
                stride_meters=stride_meters,
                note=note,
                activity_type=activity_type,
                duration_minutes=duration_minutes,
                calories=calories,
            )
            self.send_json({"record": record})
        except ValueError as exc:
            self.send_error_json(400, str(exc))
        except Exception as exc:  # pragma: no cover
            self.send_error_json(500, f"internal server error: {exc}")

    def do_DELETE(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            if not path.startswith("/records/"):
                self.send_error_json(404, "not found")
                return

            user_id = query.get("user_id", [DEFAULT_USER_ID])[0] or DEFAULT_USER_ID
            target_date = path.split("/", 2)[2]
            deleted = delete_record(user_id, target_date)
            self.send_json({"deleted": deleted})
        except ValueError as exc:
            self.send_error_json(400, str(exc))
        except Exception as exc:  # pragma: no cover
            self.send_error_json(500, f"internal server error: {exc}")

    def read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length == 0:
            return {}

        raw_body = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_common_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_static_file(self, request_path: str) -> None:
        safe_path = request_path.lstrip("/")
        file_path = (STATIC_DIR / safe_path).resolve()
        if STATIC_DIR.resolve() not in file_path.parents:
            self.send_error_json(403, "forbidden")
            return
        self.send_file(file_path)

    def send_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self.send_error_json(404, "file not found")
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if file_path.suffix == ".webmanifest":
            content_type = "application/manifest+json"
        if file_path.name == "service-worker.js":
            content_type = "text/javascript; charset=utf-8"

        body = file_path.read_bytes()
        self.send_response(200)
        self.send_common_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: int, message: str) -> None:
        self.send_json({"error": message}, status=status)

    def send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    init_db()
    server = ThreadingHTTPServer((host, port), WalkTrackerHandler)
    local_url = f"http://127.0.0.1:{port}" if host == "0.0.0.0" else f"http://{host}:{port}"
    print(f"Walk Tracker API running at {local_url}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
