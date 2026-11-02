"""Reunite: Flask + SQLite backend for a campus/community lost & found site."""
from __future__ import annotations

import io
import os
import re
import secrets
import smtplib
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from flask import Flask, abort, g, jsonify, request, send_from_directory, session, url_for
from PIL import Image, ImageOps, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parent
CATEGORIES = {"Electronics", "Bags", "Keys", "Documents", "Clothing", "Accessories", "Books", "Other"}
COLORS = {"Black", "White", "Blue", "Red", "Green", "Yellow", "Brown", "Grey", "Pink", "Purple", "Other", "Unknown"}
RATE_EVENTS = defaultdict(deque)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_error(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


def required_string(data, field, *, limit=150, minimum=1):
    value = str(data.get(field, "") or "").strip()
    if not minimum <= len(value) <= limit:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} must be {minimum}–{limit} characters.")
    return value


def image_url(filename):
    return url_for("uploaded_photo", filename=filename) if filename else None


def public_item(row):
    item = dict(row)
    return {
        "id": item["id"], "type": item["type"], "title": item["title"],
        "description": item["description"], "category": item["category"],
        "location": item["location"], "item_date": item["item_date"],
        "photo_url": image_url(item["photo_file"]), "color": item["color"],
        "status": item["status"], "created_at": item["created_at"],
        "reporter_first_name": item["reporter_name"].split()[0],
        "is_demo": bool(item["is_demo"]),
    }


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_db_path())
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def current_db_path():
    return Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data"))) / "reunite.sqlite3"


def init_db(data_dir: Path):
    with sqlite3.connect(data_dir / "reunite.sqlite3") as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('lost', 'found')),
            title TEXT NOT NULL, description TEXT NOT NULL,
            category TEXT NOT NULL, location TEXT NOT NULL,
            item_date TEXT NOT NULL, reporter_name TEXT NOT NULL,
            reporter_email TEXT NOT NULL DEFAULT '',
            reporter_phone TEXT NOT NULL DEFAULT '',
            photo_file TEXT, color TEXT NOT NULL DEFAULT 'Unknown',
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','reunited')),
            token TEXT NOT NULL UNIQUE, is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            sender_name TEXT NOT NULL, sender_contact TEXT NOT NULL,
            message TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_items_created ON items(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_items_type_status ON items(type, status);
        CREATE INDEX IF NOT EXISTS idx_inquiries_item ON inquiries(item_id);
        """)


def store_photo(file, uploads_dir: Path):
    if not file or not file.filename:
        return None
    raw = file.stream.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("Photo must be 5 MB or smaller.")
    try:
        with Image.open(io.BytesIO(raw)) as img:
            if img.width * img.height > 20_000_000:
                raise ValueError("Photo dimensions are too large. Use an image under 20 megapixels.")
            if img.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                raise ValueError("Use a JPG, PNG, WebP, or GIF photo.")
            img = ImageOps.exif_transpose(img)
            img.thumbnail((1400, 1400))
            if img.mode in ("RGBA", "P"):
                background = Image.new("RGB", img.size, "white")
                background.paste(img.convert("RGBA"), mask=img.convert("RGBA").getchannel("A"))
                img = background
            else:
                img = img.convert("RGB")
            filename = f"{uuid.uuid4().hex}.webp"
            img.save(uploads_dir / filename, "WEBP", quality=83, method=5)
            return filename
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("That image could not be processed. Upload a different photo.") from exc


def matching_items(db, source):
    opposite = "found" if source["type"] == "lost" else "lost"
    candidates = db.execute(
        "SELECT * FROM items WHERE type=? AND status='open' AND id<>? ORDER BY created_at DESC LIMIT 150",
        (opposite, source["id"]),
    ).fetchall()
    def keywords(s):
        ignored = {"the", "and", "with", "from", "this", "that", "lost", "found", "near", "some", "item", "have", "black", "white"}
        return {t for t in re.findall(r"[a-z0-9]{3,}", s.lower()) if t not in ignored}
    results = []
    for candidate in candidates:
        score, reasons = 0, []
        if candidate["category"] == source["category"]:
            score += 38
            reasons.append("Same category")
        a = keywords(source["title"] + " " + source["description"])
        b = keywords(candidate["title"] + " " + candidate["description"])
        if a and b:
            similarity = len(a & b) / max(1, len(a | b))
            if similarity:
                score += round(42 * similarity)
                reasons.append("Similar item details")
        l1 = keywords(source["location"])
        l2 = keywords(candidate["location"])
        if l1 and l2 and l1 & l2:
            score += 18
            reasons.append("Location overlap")
        if source["color"] != "Unknown" and source["color"] == candidate["color"]:
            score += 8
            reasons.append("Same color")
        if score >= 22:
            results.append({**public_item(candidate), "match_score": min(score, 98), "match_reasons": reasons})
    results.sort(key=lambda i: (-i["match_score"], i["id"]))
    return results[:5]


def send_alert(recipient, item_title, sender, message, manager_link):
    """Optional SMTP alert; messages are always available in the private dashboard."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_from = os.environ.get("SMTP_FROM")
    if not smtp_host or not smtp_from or not recipient:
        return
    try:
        mail = EmailMessage()
        mail["Subject"] = f"New message about {item_title} | Reunite"
        mail["From"] = smtp_from
        mail["To"] = recipient
        mail.set_content(f"{sender} sent a message about your report:\n\n{message}\n\nSee it in your private dashboard: {manager_link}\n")
        port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(smtp_host, port, timeout=8) as smtp:
            smtp.starttls()
            user = os.environ.get("SMTP_USER")
            if user:
                smtp.login(user, os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(mail)
    except Exception:
        # Email is best effort; no email credentials or contents are leaked to the client.
        current_app = __import__("flask").current_app
        current_app.logger.exception("Optional SMTP delivery failed")


def create_app(test_config=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    data_dir = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
    data_dir.mkdir(parents=True, exist_ok=True)
    uploads = data_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    secret_path = data_dir / ".flask_secret"
    if os.environ.get("SECRET_KEY"):
        secret = os.environ["SECRET_KEY"]
    elif secret_path.exists():
        secret = secret_path.read_text(encoding="utf-8")
    else:
        secret = secrets.token_hex(32)
        secret_path.write_text(secret, encoding="utf-8")
        try:
            secret_path.chmod(0o600)
        except OSError:
            pass
    app.config.update(
        SECRET_KEY=secret,
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)
    init_db(data_dir)

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(413)
    def too_large(error):
        return json_error("Upload is too large. Maximum photo size is 5 MB.", 413)

    @app.route("/")
    def home():
        return send_from_directory(BASE_DIR, "index.html")

    @app.route("/manage/<token>")
    def manage(token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{15,128}", token):
            abort(404)
        return send_from_directory(BASE_DIR, "manage.html")

    @app.route("/uploads/<filename>")
    def uploaded_photo(filename):
        return send_from_directory(uploads, filename, max_age=86400)

    @app.get("/api/config")
    def config():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        return jsonify({"ok": True, "csrf": session["csrf"], "max_photo_mb": 5})

    @app.before_request
    def protect_writes():
        if request.path.startswith("/api/") and request.method in {"POST", "PATCH", "DELETE"}:
            if not session.get("csrf") or not secrets.compare_digest(
                request.headers.get("X-CSRF-Token", ""), session["csrf"]
            ):
                return json_error("Security token expired. Refresh the page and try again.", 403)
            ip = request.remote_addr or "unknown"
            key = (ip, request.path)
            events = RATE_EVENTS[key]
            t = time.monotonic()
            while events and events[0] < t - 60:
                events.popleft()
            if len(events) >= 12:
                return json_error("Too many requests. Please try again shortly.", 429)
            events.append(t)

    @app.get("/api/stats")
    def stats():
        db = get_db()
        row = db.execute("SELECT COUNT(*) total, SUM(CASE WHEN status='reunited' THEN 1 ELSE 0 END) reunited, SUM(CASE WHEN type='lost' AND status='open' THEN 1 ELSE 0 END) lost, SUM(CASE WHEN type='found' AND status='open' THEN 1 ELSE 0 END) found FROM items").fetchone()
        return jsonify({"ok": True, "total": row["total"], "reunited": row["reunited"] or 0, "lost": row["lost"] or 0, "found": row["found"] or 0})

    @app.get("/api/items")
    def list_items():
        db = get_db()
        conditions, args = [], []
        type_filter = request.args.get("type", "all")
        status = request.args.get("status", "all")
        category = request.args.get("category", "all")
        q = request.args.get("q", "").strip()[:120]
        if type_filter in {"lost", "found"}:
            conditions.append("type=?"); args.append(type_filter)
        if status in {"open", "reunited"}:
            conditions.append("status=?"); args.append(status)
        if category in CATEGORIES:
            conditions.append("category=?"); args.append(category)
        if q:
            conditions.append("(title LIKE ? OR description LIKE ? OR location LIKE ? OR category LIKE ?)")
            args.extend([f"%{q}%"] * 4)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        total = db.execute(f"SELECT COUNT(*) FROM items {where}", args).fetchone()[0]
        try:
            page = max(1, min(int(request.args.get("page", "1")), 10000))
        except ValueError:
            page = 1
        order = "ASC" if request.args.get("sort") == "oldest" else "DESC"
        rows = db.execute(f"SELECT * FROM items {where} ORDER BY created_at {order}, id {order} LIMIT 12 OFFSET ?", (*args, (page - 1) * 12)).fetchall()
        return jsonify({"ok": True, "items": [public_item(r) for r in rows], "total": total, "page": page, "has_more": page * 12 < total})

    @app.post("/api/items")
    def create_item():
        fields = request.form
        try:
            item_type = required_string(fields, "type", limit=5)
            if item_type not in {"lost", "found"}:
                raise ValueError("Choose Lost or Found.")
            title = required_string(fields, "title", limit=90, minimum=3)
            description = required_string(fields, "description", limit=2000, minimum=10)
            category = required_string(fields, "category", limit=30)
            if category not in CATEGORIES:
                raise ValueError("Choose a valid category.")
            location = required_string(fields, "location", limit=140, minimum=3)
            item_date = required_string(fields, "item_date", limit=10, minimum=10)
            try:
                parsed = datetime.strptime(item_date, "%Y-%m-%d").date()
                if parsed > datetime.now().date():
                    raise ValueError("Date cannot be in the future.")
            except ValueError as exc:
                raise ValueError("Choose a valid date that isn't in the future.") from exc
            name = required_string(fields, "reporter_name", limit=100, minimum=2)
            email = str(fields.get("reporter_email", "") or "").strip()[:200]
            phone = str(fields.get("reporter_phone", "") or "").strip()[:30]
            if not email and not phone:
                raise ValueError("Add an email address or phone number so people can reach you privately.")
            if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                raise ValueError("Enter a valid email address.")
            if phone and not re.fullmatch(r"[0-9+()\-\s]{7,30}", phone):
                raise ValueError("Enter a valid phone number.")
            color = str(fields.get("color", "Unknown") or "Unknown")
            if color not in COLORS:
                color = "Unknown"
            photo = store_photo(request.files.get("photo"), uploads)
        except ValueError as exc:
            return json_error(str(exc))
        token = secrets.token_urlsafe(30)
        db = get_db()
        cur = db.execute(
            "INSERT INTO items (type,title,description,category,location,item_date,reporter_name,reporter_email,reporter_phone,photo_file,color,token,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item_type, title, description, category, location, item_date, name, email, phone, photo, color, token, now_iso()),
        )
        db.commit()
        item = db.execute("SELECT * FROM items WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify({"ok": True, "item": public_item(item), "manage_url": url_for("manage", token=token), "matches": matching_items(db, item)}), 201

    @app.get("/api/items/<int:item_id>/matches")
    def matches(item_id):
        db = get_db()
        row = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return json_error("Report not found.", 404)
        return jsonify({"ok": True, "matches": matching_items(db, row)})

    @app.post("/api/items/<int:item_id>/inquiries")
    def inquiry(item_id):
        db = get_db()
        item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            return json_error("Report not found.", 404)
        if item["status"] != "open":
            return json_error("This item has already been marked reunited.")
        fields = request.get_json(silent=True) or {}
        try:
            name = required_string(fields, "sender_name", limit=90, minimum=2)
            contact = required_string(fields, "sender_contact", limit=160, minimum=5)
            message = required_string(fields, "message", limit=1300, minimum=10)
        except ValueError as exc:
            return json_error(str(exc))
        db.execute("INSERT INTO inquiries (item_id,sender_name,sender_contact,message,created_at) VALUES (?,?,?,?,?)", (item_id, name, contact, message, now_iso()))
        db.commit()
        send_alert(item["reporter_email"], item["title"], name, message, url_for("manage", token=item["token"], _external=True))
        return jsonify({"ok": True, "message": "Message sent privately. The poster can read it in their report dashboard."}), 201

    def owned_item(token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{15,128}", token):
            return None
        return get_db().execute("SELECT * FROM items WHERE token=?", (token,)).fetchone()

    @app.get("/api/manage/<token>")
    def manage_get(token):
        item = owned_item(token)
        if not item:
            return json_error("Private report link is invalid or no longer active.", 404)
        messages = [dict(m) for m in get_db().execute("SELECT id,sender_name,sender_contact,message,created_at FROM inquiries WHERE item_id=? ORDER BY created_at DESC", (item["id"],)).fetchall()]
        return jsonify({"ok": True, "item": {**public_item(item), "reporter_name": item["reporter_name"], "reporter_email": item["reporter_email"], "reporter_phone": item["reporter_phone"]}, "inquiries": messages})

    @app.patch("/api/manage/<token>")
    def manage_update(token):
        item = owned_item(token)
        if not item:
            return json_error("Private report link is invalid.", 404)
        fields = request.get_json(silent=True) or {}
        if fields.get("status") not in {"open", "reunited"}:
            return json_error("Invalid status.")
        db = get_db()
        db.execute("UPDATE items SET status=? WHERE id=?", (fields["status"], item["id"]))
        db.commit()
        return jsonify({"ok": True, "status": fields["status"]})

    @app.delete("/api/manage/<token>")
    def manage_delete(token):
        item = owned_item(token)
        if not item:
            return json_error("Private report link is invalid.", 404)
        db = get_db()
        db.execute("DELETE FROM items WHERE id=?", (item["id"],))
        db.commit()
        if item["photo_file"]:
            (uploads / item["photo_file"]).unlink(missing_ok=True)
        return jsonify({"ok": True})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG", "0") == "1")
