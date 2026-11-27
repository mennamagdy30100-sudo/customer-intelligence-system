"""
Customer Intelligence System - Flask backend

التشغيل:
    python scripts/build_profiles.py     # مرة واحدة (أو كل ما الداتا تتغير)
    python web/app.py                    # وبعدين افتحي http://127.0.0.1:5000
"""
import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "outputs"

# مسارات صريحة عشان الموقع يشتغل مهما كان الفولدر اللي بتشغّلي منه
app = Flask(__name__, template_folder=str(HERE / "templates"), static_folder=str(HERE / "static"))
app.json.ensure_ascii = False  # عشان العربي يظهر صح في الـ JSON


def _load(name):
    path = OUT / name
    if not path.exists():
        raise SystemExit(f"الملف {path} مش موجود. شغّلي الأول: python scripts/build_profiles.py")
    return json.loads(path.read_text(encoding="utf-8"))


PROFILES = _load("customer_profiles.json")
OVERVIEW = _load("overview.json")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/overview")
def api_overview():
    return jsonify(OVERVIEW)


@app.get("/api/customers")
def api_customers():
    """بحث/فلترة/ترتيب في قايمة العملاء. كل البارامترات اختيارية."""
    q = request.args.get("q", "").strip().lower()
    city = request.args.get("city", "")
    utype = request.args.get("user_type", "")
    segment = request.args.get("segment", "")
    rfm = request.args.get("rfm", "")
    status = request.args.get("status", "")   # lapsed = غايب، at_risk = معرّض للغياب، active = نشط
    sort = request.args.get("sort", "total_spend")
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
    except ValueError:
        limit = 50

    rows = []
    for p in PROFILES.values():
        if q and q not in p["user_id"].lower():
            continue
        if city and p["city"] != city:
            continue
        if utype and p["user_type"] != utype:
            continue
        if segment and p.get("offer_segment") != segment:
            continue
        if status and p.get("status_state") != status:
            continue
        if rfm and p.get("rfm_segment") != rfm:
            continue
        rows.append({
            "user_id": p["user_id"], "city": p["city"], "user_type": p["user_type"],
            "orders_delivered": p["orders_delivered"],
            "total_spend": p.get("total_spend", 0),
            "top_category": p["top_categories"][0]["category"] if p.get("has_purchases") else None,
            "offer_segment": p.get("offer_segment", "بدون مشتريات"),
            "is_lapsed": bool(p.get("is_lapsed")),
            "status_state": p.get("status_state"),
            "rfm_segment": p.get("rfm_segment"), "rfm_code": p.get("rfm_code"),
            "days_since_last_order": p.get("days_since_last_order"),
        })

    allowed = {"total_spend", "orders_delivered", "days_since_last_order", "user_id"}
    if sort not in allowed:
        sort = "total_spend"
    # الأكبر الأول، ماعدا الاسم والأيام من آخر طلب (الأصغر الأول). القيم الفاضية دايمًا في الآخر.
    descending = sort in ("total_spend", "orders_delivered")
    with_val = sorted((r for r in rows if r[sort] is not None), key=lambda r: r[sort], reverse=descending)
    without_val = [r for r in rows if r[sort] is None]
    rows = with_val + without_val
    return jsonify({"total": len(rows), "customers": rows[:limit]})


@app.get("/api/customers/<user_id>")
def api_customer(user_id):
    p = PROFILES.get(user_id.upper())
    if p is None:
        return jsonify({"error": f"العميل {user_id} مش موجود"}), 404
    return jsonify(p)


@app.get("/api/filters")
def api_filters():
    """القيم المتاحة للفلاتر في الصفحة."""
    return jsonify({
        "cities": sorted({p["city"] for p in PROFILES.values()}),
        "user_types": sorted({p["user_type"] for p in PROFILES.values()}),
        "segments": sorted({p.get("offer_segment", "بدون مشتريات") for p in PROFILES.values()}),
    })


if __name__ == "__main__":
    app.run(debug=True)
