"""
build_profiles.py
-----------------
بيقرأ ملفات الداتا الستة من فولدر data/، وبيحسب ملف (Profile) لكل عميل،
وبيحفظ النتايج في outputs/ عشان الـ Flask يقراها.

التشغيل:  python scripts/build_profiles.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# عشان الطباعة بالعربي ما تعملش مشكلة في الـ Terminal بتاع Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

# ---------- إعدادات القواعد (تقدروا تعدلوها) ----------
OFFER_DAY_QUANTILE = 0.80      # اليوم يعتبر "يوم عروض" لو متوسط الخصم فيه ضمن أعلى 20% أيام
OFFER_DRIVEN_MIN = 0.65        # لو 65%+ من طلبات العميل عليها خصم => "بيشتري بالعروض"
FULL_PRICE_MAX = 0.35          # لو 35% أو أقل => "بيشتري بالسعر العادي"
WINBACK_DAYS = 60              # لو آخر طلب من أكتر من 60 يوم => عميل محتاج استرجاع
HIGH_CANCEL_RATE = 0.20        # نسبة إلغاء/مرتجع عالية
MIN_ORDERS_PATTERN = 8         # أقل عدد طلبات عشان نقول إن فيه "نمط" (أقل من كده الأرقام مش موثوقة)
Z_STRONG = 2.0                 # مقياس قوة الدليل: 2 أو أكتر يعني الفرق مش غالبًا صدفة
TOP_SPENDER_QUANTILE = 0.80    # أعلى 20% إنفاقًا = عملاء كبار

# "الإجازة" = الجمعة والسبت (ويك إند مصر) + الإجازات الرسمية دي.
# التواريخ اتجمعت من مصادر منشورة (officeholidays.com وcalendarlabs.com) وبعضها بيتحرك (أعياد إسلامية
# حسب رؤية الهلال، وإجازات بتتنقل ليوم الخميس). راجعيها وعدّليها لو فيه فرق.
HOLIDAYS = [
    "2025-10-06",                                                   # عيد القوات المسلحة
    "2026-01-07",                                                   # عيد الميلاد المجيد
    "2026-01-29",                                                   # عيد الثورة (25 يناير) منقولة
    "2026-03-19", "2026-03-20", "2026-03-21", "2026-03-22", "2026-03-23",   # عيد الفطر
    "2026-04-12", "2026-04-13",                                     # عيد القيامة وشم النسيم
    "2026-04-25",                                                   # عيد تحرير سيناء
    "2026-05-07",                                                   # عيد العمال (منقول)
    "2026-05-26", "2026-05-27", "2026-05-28", "2026-05-29", "2026-05-30", "2026-05-31",  # وقفة وعيد الأضحى
    "2026-06-18",                                                   # رأس السنة الهجرية
    "2026-07-02",                                                   # 30 يونيو (منقولة)
    "2026-07-23",                                                   # عيد الثورة
    "2026-08-27",                                                   # المولد النبوي
]
WEEKEND_DAYS = {"Friday", "Saturday"}

DOW_AR = {"Monday": "الاثنين", "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء",
          "Thursday": "الخميس", "Friday": "الجمعة", "Saturday": "السبت", "Sunday": "الأحد"}
DOW_ORDER = list(DOW_AR.keys())
MONTH_AR = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو",
            7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}

# ---------- 1) قراءة وربط ----------
fact = pd.read_csv(DATA / "fact_orders.csv", parse_dates=["order_date", "delivery_date"])
users = pd.read_csv(DATA / "user_dim.csv", parse_dates=["signup_date"])
prods = pd.read_csv(DATA / "product_dim.csv")
stores = pd.read_csv(DATA / "store_dim.csv")

m = (fact.merge(prods, on="item_id", how="left")
         .merge(stores, on="store_id", how="left"))
assert len(m) == len(fact)
m["dow"] = m["order_date"].dt.day_name()
m["month"] = m["order_date"].dt.month

data_end = m["order_date"].max()

# ---------- 2) تعريف "يوم العروض" ----------
# الداتا مفيهاش عمود بيقول فترة العرض، فبنعرّفها بقاعدة: الأيام اللي متوسط الخصم فيها عالي.
orders_all = m.drop_duplicates("order_id")[["order_id", "order_date", "discount"]]
daily = orders_all.groupby("order_date")["discount"].mean()
threshold = daily.quantile(OFFER_DAY_QUANTILE)
offer_days = set(daily[daily >= threshold].index)
m["is_offer_day"] = m["order_date"].isin(offer_days)

# يوم إجازة = ويك إند أو إجازة رسمية
holiday_set = set(pd.to_datetime(HOLIDAYS))
m["is_off_day"] = m["dow"].isin(WEEKEND_DAYS) | m["order_date"].isin(holiday_set)
all_days = pd.DataFrame({"d": pd.date_range(m["order_date"].min(), data_end)})
all_days["is_off_day"] = all_days["d"].dt.day_name().isin(WEEKEND_DAYS) | all_days["d"].isin(holiday_set)

# ---------- 3) على مستوى الطلب ----------
order_level = (m.groupby("order_id")
                 .agg(user_id=("user_id", "first"), order_date=("order_date", "first"),
                      status=("order_status", "first"), discount=("discount", "first"),
                      channel=("channel", "first"), store_name=("store_name", "first"),
                      dow=("dow", "first"), is_offer_day=("is_offer_day", "first"),
                      is_off_day=("is_off_day", "first"),
                      spend=("sales_amount", "sum"), items=("quantity", "sum"))
                 .reset_index())
order_level["has_discount"] = order_level["discount"] > 0

delivered_orders = order_level[order_level["status"] == "Delivered"]
delivered_lines = m[m["order_status"] == "Delivered"]

all_prods = prods.set_index("item_id")

profiles = {}
base_discount_share = float(delivered_orders["has_discount"].mean())
base_offer_day_share = float(delivered_orders["is_offer_day"].mean())

by_user_orders_all = dict(tuple(order_level.groupby("user_id")))
by_user_orders = dict(tuple(delivered_orders.groupby("user_id")))
by_user_lines = dict(tuple(delivered_lines.groupby("user_id")))

# ---- قيم مرجعية لحساب "قوة الدليل" لكل عميل ----
base_off_share = float(delivered_orders["is_off_day"].mean())
base_online_share = float((delivered_orders["channel"] == "Online").mean())
spend_by_user = delivered_orders.groupby("user_id")["spend"].sum()
top_spend_threshold = float(spend_by_user.quantile(TOP_SPENDER_QUANTILE))


def pct(x):
    return f"{round(x * 100)}%"


def zscore(k, n, base):
    """بيقيس: نسبة العميل بعيدة قد إيه عن النسبة العامة، بالنسبة لعدد طلباته. 2+ يعني غالبًا مش صدفة."""
    return (k / n - base) / ((base * (1 - base) / n) ** 0.5) if n else 0.0


# ---- هل ميل العميل لفئة معينة حقيقي ولا صدفة؟ ----
# بنحاكي مرات كتير عميل بيختار فئاته عشوائي (بنفس توزيع الفئات العام) ونشوف أعلى نسبة بتطلع صدفة.
# لو نسبة العميل الفعلية أعلى من 95% (أو 99%) من المحاكاة، يبقى الميل غالبًا حقيقي.
_rng = np.random.default_rng(42)
_cat_p = delivered_lines["category"].value_counts(normalize=True).values
_null_cache = {}


def top_share_null(n_lines):
    if n_lines not in _null_cache:
        draws = _rng.multinomial(n_lines, _cat_p, size=3000).max(axis=1) / n_lines
        _null_cache[n_lines] = (float(np.quantile(draws, 0.95)), float(np.quantile(draws, 0.99)))
    return _null_cache[n_lines]



for _, u in users.iterrows():
    uid = u["user_id"]
    o_all = by_user_orders_all.get(uid)
    o = by_user_orders.get(uid)
    l = by_user_lines.get(uid)

    p = {"user_id": uid, "city": u["city"], "user_type": u["user_type"],
         "signup_date": u["signup_date"].strftime("%Y-%m-%d")}

    total_orders_all = 0 if o_all is None else len(o_all)
    n = 0 if o is None else len(o)
    cancelled = 0 if o_all is None else int((o_all["status"] == "Cancelled").sum())
    returned = 0 if o_all is None else int((o_all["status"] == "Returned").sum())
    p["orders_total"] = total_orders_all
    p["orders_delivered"] = n
    p["cancelled"] = cancelled
    p["returned"] = returned
    p["problem_rate"] = round((cancelled + returned) / total_orders_all, 3) if total_orders_all else 0

    if n == 0:
        p["has_purchases"] = False
        profiles[uid] = p
        continue
    p["has_purchases"] = True

    # --- الإنفاق ---
    p["total_spend"] = round(float(o["spend"].sum()), 2)
    p["avg_order_value"] = round(float(o["spend"].mean()), 2)
    p["first_order"] = o["order_date"].min().strftime("%Y-%m-%d")
    p["last_order"] = o["order_date"].max().strftime("%Y-%m-%d")
    p["days_since_last_order"] = int((data_end - o["order_date"].max()).days)
    dts = o["order_date"].sort_values().diff().dt.days.dropna()
    p["avg_days_between_orders"] = round(float(dts.mean()), 1) if len(dts) else None

    # --- بيشتري إيه؟ ---
    cat = l.groupby("category")["sales_amount"].sum().sort_values(ascending=False)
    cat_share = (cat / cat.sum()).round(3)
    p["top_categories"] = [{"category": c, "spend": round(float(cat[c]), 2), "share": float(cat_share[c])}
                           for c in cat.index[:3]]
    p["all_categories"] = [{"category": c, "share": float(cat_share[c])} for c in cat.index]
    brand = l.groupby("brand")["sales_amount"].sum().sort_values(ascending=False)
    p["top_brands"] = [{"brand": b, "spend": round(float(brand[b]), 2)} for b in brand.index[:3]]
    prod = (l.groupby(["item_id", "product_name", "category"])
              .agg(qty=("quantity", "sum"), spend=("sales_amount", "sum"))
              .reset_index().sort_values(["qty", "spend"], ascending=False))
    p["top_products"] = [{"item_id": r.item_id, "product_name": r.product_name,
                          "category": r.category, "qty": int(r.qty)}
                         for r in prod.head(5).itertuples()]

    # --- بيشتري إمتى؟ ---
    dow_counts = o["dow"].value_counts()
    p["weekday_distribution"] = [{"day": DOW_AR[d], "orders": int(dow_counts.get(d, 0))} for d in DOW_ORDER]
    fav_dow = dow_counts.idxmax()
    p["favorite_weekday"] = DOW_AR[fav_dow]
    mcounts = o["order_date"].dt.month.value_counts()
    p["favorite_month"] = MONTH_AR[int(mcounts.idxmax())]
    monthly = o.groupby(o["order_date"].dt.to_period("M")).size()
    p["monthly_orders"] = [{"month": str(k), "orders": int(v)} for k, v in monthly.items()]

    # --- فين؟ ---
    ch = o["channel"].value_counts(normalize=True)
    p["online_share"] = round(float(ch.get("Online", 0)), 3)
    p["favorite_store"] = o["store_name"].value_counts().idxmax()

    # --- الخصومات ---
    disc_share = float(o["has_discount"].mean())
    offer_day_share = float(o["is_offer_day"].mean())
    p["discount_order_share"] = round(disc_share, 3)
    p["avg_discount_when_used"] = round(float(o.loc[o["has_discount"], "discount"].mean()), 3) \
        if o["has_discount"].any() else 0
    p["offer_day_share"] = round(offer_day_share, 3)
    z_disc = zscore(int(o["has_discount"].sum()), n, base_discount_share)
    if n < MIN_ORDERS_PATTERN:
        seg = "بيانات قليلة"
    elif z_disc >= Z_STRONG:
        seg = "بيتجاوب مع الخصومات"
    elif z_disc <= -Z_STRONG:
        seg = "بيشتري بالسعر العادي"
    else:
        seg = "مفيش نمط واضح"
    p["offer_segment"] = seg

    # --- الإجازات (ويك إند + إجازات رسمية) ---
    off_orders = int(o["is_off_day"].sum())
    off_share = off_orders / n
    z_off = zscore(off_orders, n, base_off_share)
    p["off_day_orders"] = off_orders
    p["off_day_share"] = round(off_share, 3)
    if n < MIN_ORDERS_PATTERN:
        off_pattern = "بيانات قليلة"
    elif z_off >= Z_STRONG:
        off_pattern = "إجازات"
    elif z_off <= -Z_STRONG:
        off_pattern = "أيام شغل"
    else:
        off_pattern = "لا يوجد"
    p["off_day_pattern"] = off_pattern

    # ================= الاستنتاجات =================
    def strength(z, enough):
        if not enough:
            return "بيانات قليلة"
        if abs(z) >= 3:
            return "واضح"
        if abs(z) >= Z_STRONG:
            return "مؤشر"
        return "لا يوجد نمط"

    enough = n >= MIN_ORDERS_PATTERN
    top_cat = p["top_categories"][0]["category"]
    top_cat_share = p["top_categories"][0]["share"]
    top_prod = p["top_products"][0]
    gap = p["avg_days_between_orders"]
    days_since = p["days_since_last_order"]
    lapsed = bool(gap) and n >= 3 and days_since > max(WINBACK_DAYS, 2 * gap)
    if not gap:
        lapsed = days_since > WINBACK_DAYS * 2
    insights = []

    # 1) بيشتري إيه
    n_lines = len(l)
    _lc = l["category"].value_counts()
    fav_cat, top_line_share = _lc.index[0], float(_lc.iloc[0]) / n_lines   # أكتر فئة من حيث عدد الأصناف
    q95, q99 = top_share_null(n_lines)
    if n_lines < 10:
        s_cat, f_cat = "بيانات قليلة", f"مشترياته قليلة ({n_lines} صنف) ومينفعش نحكم على فئة مفضلة."
    elif top_line_share > q99:
        top_cat, top_cat_share = fav_cat, float(cat_share.get(fav_cat, 0))
        s_cat, f_cat = "واضح", (f"بيميل بوضوح لفئة {top_cat}: {pct(top_line_share)} من الأصناف اللي اشتراها. "
                                f"أكتر منتج اشتراه {top_prod['product_name']} ({top_prod['qty']} قطعة).")
    elif top_line_share > q95:
        top_cat, top_cat_share = fav_cat, float(cat_share.get(fav_cat, 0))
        s_cat, f_cat = "مؤشر", f"غالبًا بيميل لفئة {top_cat} ({pct(top_line_share)} من الأصناف)، بس الدليل مش قوي."
    else:
        s_cat, f_cat = "لا يوجد نمط", (f"بيشتري من فئات كتير ومفيش فئة مفضلة واضحة. أكتر فئة اشتراها {fav_cat} "
                                       f"({pct(top_line_share)} من الأصناف) وده قريب من اللي بيحصل صدفة لعدد مشترياته.")
    p["category_signal"] = s_cat
    p["focus_category"] = top_cat
    insights.append({"topic": "بيشتري إيه؟", "finding": f_cat, "strength": s_cat, "evidence": f"{n_lines} صنف في {n} طلب"})

    # 2) بيشتري إمتى؟ (إجازات ولا أيام شغل)
    base_txt = pct(base_off_share)
    if off_pattern == "إجازات":
        f_off = f"بيشتري في الإجازات والويك إند أكتر من المعتاد: {pct(off_share)} من طلباته، مقابل {base_txt} للعملاء عمومًا."
    elif off_pattern == "أيام شغل":
        f_off = f"بيشتري في أيام الشغل أكتر من الإجازات: {pct(off_share)} بس من طلباته في الإجازات، مقابل {base_txt} للعملاء عمومًا."
    elif off_pattern == "لا يوجد":
        f_off = (f"مفيش دليل كفاية على نمط: {pct(off_share)} من طلباته في الإجازات (المعتاد {base_txt})، "
                 f"والفرق ممكن يكون صدفة لأن عدد طلباته {n}.")
    else:
        f_off = f"طلباته قليلة ({n}) ومينفعش نحكم على نمط الإجازات."
    insights.append({"topic": "بيشتري إمتى؟", "finding": f_off, "strength": strength(z_off, enough),
                     "evidence": f"{off_orders} طلب في الإجازات من {n}"})

    # 3) تكرار الطلب
    if gap:
        nxt = (o["order_date"].max() + pd.Timedelta(days=round(gap))).strftime("%Y-%m-%d")
        overdue = (data_end - pd.Timestamp(nxt)).days
        if lapsed:
            tail = " وده أطول من المعتاد عنده."
        elif overdue > 0:
            tail = f"، وكان المتوقع يطلب حوالي {nxt} (متأخر {overdue} يوم)."
        else:
            tail = f"، والطلب الجاي المتوقع حوالي {nxt}."
        f_freq = f"بيطلب كل {gap:.0f} يوم تقريبًا. آخر طلب من {days_since} يوم" + tail
        p["expected_next_order"] = nxt
    else:
        f_freq = f"عمل طلب واحد بس، وآخر طلب من {days_since} يوم."
    insights.append({"topic": "تكرار الشراء", "finding": f_freq,
                     "strength": "واضح" if n >= 5 else "بيانات قليلة", "evidence": f"{n} طلب"})
    p["is_lapsed"] = bool(lapsed)
    # حالة العميل: نشط / معرّض للغياب / غايب، وموضعه على مقياس من 0 لـ 100 للعرض في الموقع
    thr = max(WINBACK_DAYS, 2 * gap) if (gap and n >= 3) else WINBACK_DAYS * 2
    act_end = min(max(gap or 30, 14), thr * 0.6)
    if lapsed:
        state = "lapsed"
    elif days_since <= act_end:
        state = "active"
    else:
        state = "at_risk"
    if days_since <= act_end:
        pos = 33 * days_since / act_end
    elif days_since <= thr:
        pos = 33 + 33 * (days_since - act_end) / (thr - act_end)
    else:
        pos = 66 + 34 * min((days_since - thr) / thr, 1)
    p["status_state"], p["status_pos"], p["lapse_after_days"] = state, round(pos, 1), int(thr)

    # آخر الطلبات (بكل الحالات) للتسلسل الزمني
    _ro = o_all.sort_values("order_date", ascending=False).head(8)
    p["recent_orders"] = [{"order_id": r.order_id, "date": r.order_date.strftime("%Y-%m-%d"), "status": r.status,
                           "spend": round(float(r.spend), 2), "items": int(r.items),
                           "discount": float(r.discount), "store": r.store_name} for r in _ro.itertuples()]

    # 4) الخصومات
    if seg == "بيتجاوب مع الخصومات":
        f_disc = f"بيتجاوب مع الخصومات: {pct(disc_share)} من طلباته عليها خصم، مقابل {pct(base_discount_share)} للعملاء عمومًا."
    elif seg == "بيشتري بالسعر العادي":
        f_disc = f"بيشتري غالبًا بالسعر العادي: {pct(disc_share)} بس من طلباته عليها خصم، مقابل {pct(base_discount_share)} للعملاء عمومًا."
    elif seg == "مفيش نمط واضح":
        f_disc = (f"مفيش دليل كفاية على نمط: {pct(disc_share)} من طلباته عليها خصم (المعتاد {pct(base_discount_share)})، "
                  f"والفرق ممكن يكون صدفة لأن عدد طلباته {n}.")
    else:
        f_disc = f"طلباته قليلة ({n}) ومينفعش نحكم على تعامله مع الخصومات."
    insights.append({"topic": "الخصومات", "finding": f_disc, "strength": strength(z_disc, enough),
                     "evidence": f"{int(o['has_discount'].sum())} طلب بخصم من {n}"})

    # 5) القناة (أونلاين/فروع) - بس لو الفرق عن المعتاد كبير بشكل مش صدفة
    online_orders = int((o["channel"] == "Online").sum())
    z_on = zscore(online_orders, n, base_online_share)
    if enough and z_on >= 3:
        insights.append({"topic": "قناة الشراء", "finding": f"بيطلب أونلاين أكتر من المعتاد: {pct(p['online_share'])} من طلباته مقابل {pct(base_online_share)} للعملاء عمومًا.",
                         "strength": "مؤشر", "evidence": f"{online_orders} طلب أونلاين من {n}"})
    elif enough and z_on <= -3:
        insights.append({"topic": "قناة الشراء", "finding": f"بيشتري من الفروع أكتر من المعتاد: {pct(1 - p['online_share'])} من طلباته من الفروع مقابل {pct(1 - base_online_share)} للعملاء عمومًا.",
                         "strength": "مؤشر", "evidence": f"{n - online_orders} طلب من الفروع من {n}"})

    # 6) جودة الخدمة
    high_problem = p["problem_rate"] >= HIGH_CANCEL_RATE and total_orders_all >= MIN_ORDERS_PATTERN
    if high_problem:
        insights.append({"topic": "جودة الخدمة", "finding": f"{pct(p['problem_rate'])} من طلباته اتلغت أو اترجعت ({cancelled + returned} من {total_orders_all}).",
                         "strength": "واضح", "evidence": f"{total_orders_all} طلب"})
    p["insights"] = insights

    # ================= العروض المقترحة =================
    offers = []
    if high_problem:
        offers.append({"type": "service", "title": "اتصال متابعة قبل أي عرض",
                       "detail": "نسبة الإلغاء والمرتجع عنده عالية. الأفضل نعرف السبب ونصلحه، وبعدها نبعتله العرض.",
                       "why": "الإلغاء المتكرر معناه مشكلة في الخدمة، والعرض لوحده مش هيحلها."})

    # أ) كوبون الفاتورة الجاية
    # الداتا بتقول إن الخصم مابيزوّدش حجم الطلب (شوفي "الصورة العامة" في الموقع)،
    # فالخصم بنخصصه للعميل اللي غاب بس، ومش للعميل النشط.
    is_big = p["total_spend"] >= top_spend_threshold
    if lapsed:
        pct_off = 15 if is_big else 10
        offers.append({"type": "next_invoice", "title": f"كوبون استرجاع {pct_off}% على الفاتورة الجاية",
                       "detail": (f"صالح 14 يوم. العميل غايب من {days_since} يوم وده أكتر من معتاده"
                                  + (" وهو من أعلى 20% عملاء إنفاقًا." if is_big else ".")
                                  + " يُفضّل نجرّبه على نص العملاء الغايبين ونقارن بالنص التاني."),
                       "why": "العميل اللي غاب عن معتاده هو اللي الخصم ممكن يفرق معاه، وده اقتراح للتجربة مش مضمون."})
    elif is_big:
        offers.append({"type": "next_invoice", "title": "امتياز بدون خصم (توصيل مجاني أو أولوية في المنتجات الجديدة)",
                       "detail": f"عميل كبير ونشط (إجمالي {p['total_spend']:,.0f}، آخر طلب من {days_since} يوم).",
                       "why": "هو بيشتري من نفسه، والخصم عمومًا مابيزوّدش حجم الطلب في الداتا، فبلاش نخسر هامش على عميل مش محتاج."})
    else:
        thr = int(round(p["avg_order_value"] * 1.15, -1)) or int(p["avg_order_value"])
        offers.append({"type": "next_invoice", "title": f"خصم 5% على الفاتورة الجاية لو زادت عن {thr:,}",
                       "detail": f"متوسط طلبه {p['avg_order_value']:,.0f}. الهدف نزوّد قيمة فاتورته شوية.",
                       "why": "الخصم مربوط بحد أدنى فوق متوسطه، فبياخده بس لو زوّد. اقتراح للتجربة."})

    # ب) عرض على فئته المفضلة (بس لو الميل ليها حقيقي، ومش على منتج بعينه لأن تكرار نفس المنتج مش واضح في الداتا)
    if s_cat in ("واضح", "مؤشر"):
        offers.append({"type": "product_offer", "title": f"عرض على فئة {top_cat}",
                       "detail": f"مثلًا: خصم 10% على أي منتج من {top_cat}. أكتر منتج اشتراه {top_prod['product_name']}.",
                       "why": f"{pct(top_line_share)} من الأصناف اللي اشتراها من الفئة دي، وده أعلى من اللي بيحصل صدفة لعدد مشترياته."})

    # ج) توقيت الإرسال (بس لو فيه نمط)
    if off_pattern == "إجازات":
        offers.append({"type": "timing", "title": "ابعتله العرض قبل الإجازة أو الويك إند بيوم",
                       "detail": "نسبة طلباته في الإجازات أعلى من المعتاد.",
                       "why": f"{pct(off_share)} من طلباته في الإجازات مقابل {base_txt} للعملاء عمومًا."})
    elif off_pattern == "أيام شغل":
        offers.append({"type": "timing", "title": "ابعتله العرض في أيام الأسبوع (مش الإجازات)",
                       "detail": "طلباته بتكون في أيام الشغل أكتر.",
                       "why": f"{pct(off_share)} بس من طلباته في الإجازات مقابل {base_txt} للعملاء عمومًا."})

    # ج2) قناة الإرسال (الفرق عن المعتاد واضح إحصائيًا في الداتا دي)
    if enough and z_on >= 3:
        offers.append({"type": "channel", "title": "ابعتله العرض برابط المتجر الأونلاين",
                       "detail": "طلباته أونلاين أكتر من المعتاد، فالعرض اللي بيوصله على الأونلاين هو اللي هيستخدمه.",
                       "why": f"{pct(p['online_share'])} من طلباته أونلاين مقابل {pct(base_online_share)} للعملاء عمومًا."})
    elif enough and z_on <= -3:
        offers.append({"type": "channel", "title": "ابعتله العرض كقسيمة تُستخدم في الفروع",
                       "detail": "بيشتري من الفروع أكتر من المعتاد.",
                       "why": f"{pct(1 - p['online_share'])} من طلباته من الفروع مقابل {pct(1 - base_online_share)} للعملاء عمومًا."})

    # د) منتجات جديدة من فئته
    bought = set(l["item_id"])
    pool = prods[(prods["category"] == top_cat) & (~prods["item_id"].isin(bought))]
    p["suggested_products"] = [{"item_id": r.item_id, "product_name": r.product_name,
                                "category": r.category, "brand": r.brand} for r in pool.head(4).itertuples()]
    if len(pool) and s_cat in ("واضح", "مؤشر"):
        offers.append({"type": "try_new", "title": f"اقترح عليه منتجات جديدة من {top_cat}",
                       "detail": "لسه ما جرّبهاش: " + "، ".join(pool["product_name"].head(3).tolist()),
                       "why": "هو بيحب الفئة دي، فاحتمال يجرّب منتجات جديدة منها أعلى."})
    p["offers"] = offers[:5]

    profiles[uid] = p

# ---------- الأنماط الفردية مقابل الصدفة ----------
# لو مفيش أي نمط حقيقي، حوالي 4.5% من العملاء هيطلعلهم "نمط" بالصدفة. لو العدد الفعلي قريب من كده،
# يبقى الأنماط الفردية من النوع ده مش موثوقة، ونقول ده في ملف كل عميل بدل ما نعرضها كحقيقة.
_elig = [p for p in profiles.values() if p.get("orders_delivered", 0) >= MIN_ORDERS_PATTERN]
_chance = len(_elig) * 0.0455
_off_flag = sum(p["off_day_pattern"] in ("إجازات", "أيام شغل") for p in _elig)
_disc_flag = sum(p["offer_segment"] in ("بيتجاوب مع الخصومات", "بيشتري بالسعر العادي") for p in _elig)
_cat_flag = sum(p.get("category_signal") in ("واضح", "مؤشر") for p in _elig)
_noisy = {"cat": _cat_flag <= _chance * 1.3, "off": _off_flag <= _chance * 1.3, "disc": _disc_flag <= _chance * 1.3}
_NOTE = " (لكن على مستوى كل العملاء، الأنماط من النوع ده قريبة من الصدفة في الداتا دي، فاعتبريها إشارة مش حقيقة.)"
_topic_key = {"بيشتري إيه؟": "cat", "بيشتري إمتى؟": "off", "الخصومات": "disc"}
_offer_key = {"product_offer": "cat", "try_new": "cat", "timing": "off"}

for p in profiles.values():
    if not p.get("has_purchases"):
        continue
    for i in p["insights"]:
        k = _topic_key.get(i["topic"])
        if k and _noisy[k] and i["strength"] in ("واضح", "مؤشر"):
            i["strength"] = "غالبًا صدفة"
            i["finding"] = i["finding"].replace("بيميل بوضوح لفئة", "نسبة الأصناف عنده أعلى من المعتاد في فئة").replace("غالبًا بيميل لفئة", "نسبة الأصناف عنده أعلى من المعتاد في فئة") + _NOTE
    for of in p["offers"]:
        k = _offer_key.get(of["type"])
        if k and _noisy[k]:
            of["why"] = "اقتراح تجريبي بس: الأنماط الفردية من النوع ده قريبة من الصدفة في الداتا دي، فجرّبوه على نطاق صغير قبل ما تعتمدوا عليه."

    # الخلاصة (بتتكتب هنا عشان تعرف الأنماط المشكوك فيها)
    n = p["orders_delivered"]
    parts = [f"عميل {p['user_type']} من {p['city']}، عمل {n} طلب مُسلَّم بإجمالي {p['total_spend']:,.0f} (متوسط الطلب {p['avg_order_value']:,.0f})."]
    if p["category_signal"] in ("واضح", "مؤشر") and not _noisy["cat"]:
        parts.append(f"بيميل لفئة {p['focus_category']}.")
    else:
        parts.append("مفيش فئة مفضلة واضحة عنده.")
    if not _noisy["off"] and p["off_day_pattern"] == "إجازات":
        parts.append("بيشتري في الإجازات والويك إند أكتر من المعتاد.")
    elif not _noisy["off"] and p["off_day_pattern"] == "أيام شغل":
        parts.append("بيشتري في أيام الشغل أكتر من الإجازات.")
    else:
        parts.append("مفيش نمط واضح بين الإجازات وأيام الشغل.")
    if p["is_lapsed"]:
        parts.append(f"غايب عن معتاده (آخر طلب من {p['days_since_last_order']} يوم).")
    elif p.get("avg_days_between_orders"):
        parts.append(f"بيطلب تقريبًا كل {p['avg_days_between_orders']:.0f} يوم.")
    main_offer = next((x for x in p["offers"] if x["type"] != "service"), p["offers"][0])
    parts.append(f"العرض الأنسب: {main_offer['title']}.")
    p["summary"] = " ".join(parts)

# ---------- 4) ملخص عام للـ Dashboard ----------
lines_d = delivered_lines
overview = {
    "data_range": {"from": m["order_date"].min().strftime("%Y-%m-%d"), "to": data_end.strftime("%Y-%m-%d")},
    "customers": int(users.shape[0]),
    "orders_total": int(order_level.shape[0]),
    "orders_delivered": int(len(delivered_orders)),
    "revenue_delivered": round(float(delivered_orders["spend"].sum()), 2),
    "avg_order_value": round(float(delivered_orders["spend"].mean()), 2),
    "status_counts": order_level["status"].value_counts().to_dict(),
    "discount_order_share": round(base_discount_share, 3),
    "offer_day_rule": {"quantile": OFFER_DAY_QUANTILE, "threshold_avg_discount": round(float(threshold), 4),
                       "offer_days_count": len(offer_days), "total_days": int(daily.shape[0])},
    "offer_vs_normal": {
        "offer_days": {"orders": int(delivered_orders["is_offer_day"].sum()),
                       "avg_order_value": round(float(delivered_orders.loc[delivered_orders["is_offer_day"], "spend"].mean()), 2)},
        "normal_days": {"orders": int((~delivered_orders["is_offer_day"]).sum()),
                        "avg_order_value": round(float(delivered_orders.loc[~delivered_orders["is_offer_day"], "spend"].mean()), 2)},
    },
    "segments": pd.Series([p.get("offer_segment", "بدون مشتريات") for p in profiles.values()]).value_counts().to_dict(),
    "top_categories": [{"category": c, "spend": round(float(v), 2)}
                       for c, v in lines_d.groupby("category")["sales_amount"].sum().sort_values(ascending=False).items()],
    "monthly_orders": [{"month": str(k), "orders": int(v)}
                       for k, v in delivered_orders.groupby(delivered_orders["order_date"].dt.to_period("M")).size().items()],
    "weekday_orders": [{"day": DOW_AR[d], "orders": int((delivered_orders["dow"] == d).sum())} for d in DOW_ORDER],
    "monthly_revenue": [{"month": str(k), "revenue": round(float(v), 2)}
                        for k, v in delivered_orders.groupby(delivered_orders["order_date"].dt.to_period("M"))["spend"].sum().items()],
    "weekly_orders": [{"week": k.strftime("%Y-%m-%d"), "orders": int(v)}
                      for k, v in delivered_orders.set_index("order_date").resample("W-SAT").size().items()],
    "channel_orders": delivered_orders["channel"].value_counts().to_dict(),
}

# الإجازات مقابل أيام الشغل (على مستوى الشركة)
_per_day = delivered_orders.groupby("order_date").size()
all_days["orders"] = all_days["d"].map(_per_day).fillna(0)
_off = all_days[all_days["is_off_day"]]
_work = all_days[~all_days["is_off_day"]]
_opd_off, _opd_work = float(_off["orders"].mean()), float(_work["orders"].mean())
if _opd_off >= _opd_work * 1.10:
    _verdict = "الطلبات في الإجازات أعلى من أيام الشغل"
elif _opd_off <= _opd_work * 0.90:
    _verdict = "الطلبات في الإجازات أقل من أيام الشغل"
else:
    _verdict = "مفيش فرق واضح بين الإجازات وأيام الشغل"
overview["offday_vs_workday"] = {
    "off_days": int(len(_off)), "work_days": int(len(_work)),
    "orders_per_off_day": round(_opd_off, 1), "orders_per_work_day": round(_opd_work, 1),
    "verdict": _verdict,
    "definition": "الإجازة = الجمعة والسبت + الإجازات الرسمية",
}
overview["off_day_patterns"] = pd.Series([p.get("off_day_pattern", "بدون مشتريات") for p in profiles.values()]).value_counts().to_dict()
overview["holidays"] = HOLIDAYS

# ---- الصورة العامة: أهم اللي الداتا بتقوله (بتتحسب من الداتا، مش مكتوبة بإيدي) ----
_ol = order_level  # كل الحالات
_d0 = m["order_date"].min()
_act_first = int(_ol[_ol["order_date"] <= _d0 + pd.Timedelta(days=91)]["user_id"].nunique())
_act_last = int(_ol[_ol["order_date"] >= data_end - pd.Timedelta(days=91)]["user_id"].nunique())
_lapsed_n = sum(1 for p in profiles.values() if p.get("is_lapsed"))
_dd = delivered_orders.groupby("has_discount").agg(items=("items", "mean"), value=("spend", "mean"))
_items_d, _items_n = float(_dd.loc[True, "items"]), float(_dd.loc[False, "items"])
_val_d, _val_n = float(_dd.loc[True, "value"]), float(_dd.loc[False, "value"])

_title_off = ("الإجازات بتزوّد المبيعات" if _opd_off >= _opd_work * 1.10
              else "الإجازات بتقلّل المبيعات" if _opd_off <= _opd_work * 0.90
              else "مفيش فرق واضح في المبيعات بين الإجازات وأيام الشغل")
overview["customer_status"] = {
    "active": sum(p.get("status_state") == "active" for p in profiles.values()),
    "at_risk": sum(p.get("status_state") == "at_risk" for p in profiles.values()),
    "lapsed": sum(p.get("status_state") == "lapsed" for p in profiles.values()),
    "no_orders": sum(not p.get("has_purchases") for p in profiles.values()),
}

overview["key_findings"] = [
    {"title": _title_off,
     "strength": "واضح",
     "detail": (f"في الإجازات (الجمعة والسبت والأعياد الرسمية) بنبيع {_opd_off:.0f} طلب في اليوم، "
                f"وفي أيام الشغل {_opd_work:.0f} طلب في اليوم."),
     "action": ("الإجازات مش موسم مبيعات في الداتا دي، فمفيش داعي لحملة عروض عامة مربوطة بيها."
                if _opd_off < _opd_work * 1.10 else
                "الإجازات موسم مبيعات حقيقي، فجهّزوا عروضكم قبلها بيوم.")},
    {"title": "عملاء كتير وقفوا يشتروا",
     "strength": "واضح",
     "detail": (f"العملاء اللي طلبوا في أول 3 شهور: {_act_first:,}، وفي آخر 3 شهور: {_act_last:,}. "
                f"و{_lapsed_n:,} عميل غايب أكتر من معتاده."),
     "action": "ده أهم فرصة: ابعت عرض استرجاع للعملاء الغايبين (فلتر 'غايب عن معتاده' في القايمة)."},
    {"title": "الخصم مابيزوّدش حجم الطلب",
     "strength": "مؤشر",
     "detail": (f"الطلب بخصم فيه {_items_d:.1f} قطعة بمتوسط قيمة {_val_d:,.0f}، "
                f"والطلب من غير خصم فيه {_items_n:.1f} قطعة بمتوسط قيمة {_val_n:,.0f}. "
                f"يعني الخصم قلّل قيمة الطلب ومازوّدش عدد القطع."),
     "action": "بلاش خصومات عامة، وخلّي الخصم للعميل الغايب أو بحد أدنى للفاتورة. وجرّبوا ده على مجموعة صغيرة الأول."},
    {"title": "أنماط الإجازات والخصومات والفئات المفضلة لكل عميل قريبة من الصدفة",
     "strength": "واضح",
     "detail": (f"من {len(_elig):,} عميل طلباتهم كفاية للحكم: طلع {_off_flag} عميل بنمط في الإجازات، "
                f"و{_disc_flag} بنمط في الخصومات، و{_cat_flag} بفئة مفضلة. "
                f"ولو مفيش أي نمط حقيقي، المتوقع صدفة حوالي {_chance:.0f} عميل في كل واحدة من التلاتة."),
     "action": "الأنماط الفردية دي بتتاخد كإشارة مش كحقيقة. استخدمي الإجراءات اللي اتأكدت من الداتا "
               "(العملاء الغايبين وشكل الطلب)، وكل ما تضيفي شهور أكتر من الطلبات هتبان الأنماط الفردية أوضح."},
]

# فحص: هل اختلاف العملاء في استخدام الخصومات حقيقي ولا عشوائي؟
# لو الانحراف المعياري الفعلي قريب من المتوقع لو الخصم عشوائي بالكامل، يبقى الإشارة ضعيفة.
_heavy = [p for p in profiles.values() if p.get("orders_delivered", 0) >= 20]
if len(_heavy) >= 30:
    _obs = float(pd.Series([p["discount_order_share"] for p in _heavy]).std())
    _avg_n = float(pd.Series([p["orders_delivered"] for p in _heavy]).mean())
    _exp = (base_discount_share * (1 - base_discount_share) / _avg_n) ** 0.5
    overview["discount_behavior_check"] = {
        "customers_checked": len(_heavy),
        "observed_spread": round(_obs, 3),
        "expected_if_random": round(_exp, 3),
        "signal": "ضعيفة" if _obs < _exp * 1.25 else "واضحة",
    }

# ---------- RFM: الشرائح + بروفايل كل شريحة + الإجراءات ----------
RFM_SEGMENTS = [
    # key, الاسم, الهدف, الإجراءات
    ("champions", "أفضل العملاء (Champions)", "حافظي عليهم", ["معاملة مميزة وأولوية في العروض الجديدة", "تواصل دافئ", "من غير خصومات مش لازمة"]),
    ("loyal", "عملاء أوفياء (Loyal)", "زوّدي حجم السلة", ["بيع مكمّل (Cross-sell)", "عروض باقات", "ترشيح فئات جديدة"]),
    ("potential", "واعدين (Potential)", "زوّدي تكرار الشراء", ["حافز للطلب الثاني", "تذكيرات بتبني عادة الشراء"]),
    ("at_risk", "معرّضين للفقد (At Risk)", "رجّعيهم", ["تذكير الأول", "حافز مختار بس", "رسالة رجوع شخصية"]),
    ("lost", "ضعاف / غايبين (Lost)", "اصرفي بحذر", ["حملات سعر بس لما العائد يستاهل"]),
]
_rf = pd.DataFrame({
    "user_id": spend_by_user.index,
    "recency": [profiles[u]["days_since_last_order"] for u in spend_by_user.index],
    "frequency": delivered_orders.groupby("user_id").size().reindex(spend_by_user.index).values,
    "monetary": spend_by_user.values,
})
def _score(series, higher_better=True):
    r = series.rank(method="first", ascending=higher_better)  # أعلى رتبة = أحسن
    return pd.qcut(r, 4, labels=[1, 2, 3, 4]).astype(int)
_rf["R"] = _score(_rf["recency"], higher_better=False)
_rf["F"] = _score(_rf["frequency"])
_rf["M"] = _score(_rf["monetary"])
def _seg(r, f):
    if f >= 3 and r >= 3: return "champions"
    if f >= 3 and r == 2: return "loyal"
    if f >= 3 and r == 1: return "at_risk"
    if r >= 3: return "potential"
    return "lost"
_rf["segment"] = [_seg(r, f) for r, f in zip(_rf["R"], _rf["F"])]
_seg_of = dict(zip(_rf["user_id"], _rf["segment"]))
_rf_of = _rf.set_index("user_id")
for uid, pr in profiles.items():
    if uid in _rf_of.index:
        row = _rf_of.loc[uid]
        pr["rfm"] = {"r": int(row["R"]), "f": int(row["F"]), "m": int(row["M"])}
        pr["rfm_code"] = f'{int(row["R"])}{int(row["F"])}{int(row["M"])}'
        pr["rfm_segment"] = row["segment"]
    else:
        pr["rfm"] = None; pr["rfm_code"] = None; pr["rfm_segment"] = None

_do = delivered_orders.assign(seg=delivered_orders["user_id"].map(_seg_of))
_dl = delivered_lines.assign(seg=delivered_lines["user_id"].map(_seg_of))
_total_rev = float(_do["spend"].sum())
_all_cat = (_dl.groupby("category")["sales_amount"].sum() / _dl["sales_amount"].sum())
_all_online = float((_do["channel"] == "Online").mean())
_all_disc = float(_do["has_discount"].mean())
_users_idx = users.set_index("user_id")
_days_span = max((data_end - m["order_date"].min()).days, 1)
rfm_segments = []
for key, name, goal, acts in RFM_SEGMENTS:
    ids = _rf.loc[_rf["segment"] == key, "user_id"]
    o = _do[_do["seg"] == key]; l = _dl[_dl["seg"] == key]
    n = int(len(ids))
    if n == 0:
        continue
    cat = (l.groupby("category")["sales_amount"].sum() / l["sales_amount"].sum()).sort_values(ascending=False)
    city = _users_idx.loc[ids, "city"].value_counts(normalize=True)
    utype = _users_idx.loc[ids, "user_type"].value_counts(normalize=True)
    rfm_segments.append({
        "key": key, "name": name, "goal": goal, "actions": acts,
        "customers": n, "customer_share": round(n / len(_rf), 4),
        "revenue": round(float(o["spend"].sum()), 2), "revenue_share": round(float(o["spend"].sum()) / _total_rev, 4),
        "avg_order_value": round(float(o["spend"].mean()), 1),
        "orders_per_customer": round(len(o) / n, 1),
        "orders_per_year": round(len(o) / n * 365 / _days_span, 1),
        "avg_recency": round(float(_rf.loc[_rf["segment"] == key, "recency"].mean()), 0),
        "discount_share": round(float(o["has_discount"].mean()), 4),
        "online_share": round(float((o["channel"] == "Online").mean()), 4),
        "top_categories": [{"category": c, "share": round(float(v), 4), "overall": round(float(_all_cat[c]), 4)} for c, v in cat.head(5).items()],
        "top_city": {"name": city.index[0], "share": round(float(city.iloc[0]), 4)},
        "top_user_type": {"name": utype.index[0], "share": round(float(utype.iloc[0]), 4)},
    })
_hi_m_risk = int(((_rf["segment"] == "at_risk") & (_rf["M"] >= 3)).sum())
overview["rfm"] = {
    "segments": rfm_segments,
    "baseline": {"discount_share": round(_all_disc, 4), "online_share": round(_all_online, 4)},
    "scoring_note": "كل درجة من 1 لـ 4 بتتحسب بترتيب العملاء ببعض (ربع الأحسن = 4). الشريحة نسبية: بتقارن العميل بباقي العملاء، مش بمعيار خارجي.",
    "cards": {
        "priority_audience": {"title": "الجمهور الأهم", "value": "معرّضين للفقد وإنفاقهم عالي", "count": _hi_m_risk},
        "low_cost_action": {"title": "أرخص إجراء", "value": "تذكير قبل أي خصم"},
        "budget_protection": {"title": "حماية الميزانية", "value": "من غير كوبونات عامة"},
    },
}

(OUT / "customer_profiles.json").write_text(json.dumps(profiles, ensure_ascii=False), encoding="utf-8")
(OUT / "overview.json").write_text(json.dumps(overview, ensure_ascii=False, indent=1), encoding="utf-8")

# نسخة CSV مسطحة للتحليل في Excel/Jupyter
flat_cols = ["user_id", "rfm_code", "rfm_segment", "city", "user_type", "orders_delivered", "total_spend", "avg_order_value",
             "days_since_last_order", "avg_days_between_orders", "favorite_weekday", "favorite_month",
             "online_share", "discount_order_share", "offer_day_share", "offer_segment", "problem_rate"]
flat = pd.DataFrame([{**{k: p.get(k) for k in flat_cols},
                      "top_category": p["top_categories"][0]["category"] if p.get("has_purchases") else None}
                     for p in profiles.values()])
flat.to_csv(OUT / "customer_profiles.csv", index=False, encoding="utf-8-sig")

print(f"Profiles: {len(profiles):,}  |  offer days: {len(offer_days)}/{len(daily)}")
print("Segments:", overview["segments"])
