# utils/formatting.py
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
import json  # ★ 文字列JSON対応で追加

MEAL_ORDER = ["morning", "noon", "night", "snack"]
MEAL_LABEL = {
    "morning": "朝食（morning）",
    "noon": "昼食（noon）",
    "night": "夕食（night）",
    "snack": "間食（snack）",
}

def _fmt_num(x: Optional[float], suffix: str = "", ndigits: int = 1) -> str:
    if x is None:
        return "-"
    try:
        return f"{round(float(x), ndigits)}{suffix}"
    except (TypeError, ValueError):
        return "-"

def _parse_date(date_str: str) -> str:
    if not date_str:
        return ""
    core = date_str[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(core, fmt).strftime("%Y/%m/%d")
        except ValueError:
            continue
    return date_str

def _date_key(s: str) -> str:
    if not s:
        return ""
    return s[:10].replace("/", "-")

def _pick_anthro_for_date(anthro_json: Dict[str, Any], date_str: str) -> Dict[str, Optional[float]]:
    items = (anthro_json or {}).get("data") or []
    target = _date_key(date_str)
    for row in items:
        rdate = _date_key(str(row.get("date", "")))
        if rdate == target:
            return {"weight": row.get("weight"), "fat": row.get("fat")}
    return {"weight": None, "fat": None}

def _collect_meals(meal_with_basis: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    grouped = {k: [] for k in MEAL_ORDER}
    items = (meal_with_basis or {}).get("meal_histories") \
        or (meal_with_basis or {}).get("meals") \
        or (meal_with_basis or {}).get("records") \
        or []
    for item in items or []:
        mtype = (item.get("meal_type") or item.get("type") or "").strip()
        if mtype in grouped:
            grouped[mtype].append(item)
    return grouped

def _get_basis(meal_with_basis: Dict[str, Any]) -> Dict[str, Optional[float]]:
    b = (meal_with_basis or {}).get("basis") or {}
    allv = b.get("all") if isinstance(b.get("all"), dict) else b
    # 代替キーも一応吸収
    allv = allv or (meal_with_basis.get("goal") or meal_with_basis.get("targets") or {})
    return {
        "calorie": allv.get("calorie") or allv.get("kcal"),
        "protein": allv.get("protein") or allv.get("protein_g"),
        "fat": allv.get("fat") or allv.get("fat_g"),
        "carbohydrate": allv.get("carbohydrate") or allv.get("carb") or allv.get("carbs_g"),
    }

def _get_summary(meal_with_basis: Dict[str, Any]) -> Dict[str, Optional[float]]:
    s = (meal_with_basis or {}).get("meal_histories_summary") or {}
    allv = s.get("all") if isinstance(s.get("all"), dict) else s
    allv = allv or meal_with_basis.get("summary") or meal_with_basis.get("totals") or {}
    return {
        "calorie": allv.get("calorie") or allv.get("kcal"),
        "protein": allv.get("protein"),
        "fat": allv.get("fat"),
        "carbohydrate": allv.get("carbohydrate") or allv.get("carb") or allv.get("carbs"),
    }

def _normalize_anthropometric(anthropometric: Any) -> Dict[str, Any]:
    if isinstance(anthropometric, list):
        return {"data": anthropometric}
    return anthropometric or {}

def _unwrap_meal_container(obj: Union[dict, list, str]) -> Union[dict, list]:
    """
    Calomealが { "meal_with_basis": {... or [...] } の形や
    文字列JSONで返すケースに対応。ラッパーと文字列を処理。
    """
    # ラッパー解除
    if isinstance(obj, dict) and "meal_with_basis" in obj:
        obj = obj.get("meal_with_basis")

    # ★ 文字列JSONならパース
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            # パース失敗ならそのまま返す（後段で空扱いに落ちる）
            return obj
    return obj

def _select_meal_object(meal_with_basis: Any, date_str: str) -> Dict[str, Any]:
    """
    - ラッパー 'meal_with_basis' を剥がす
    - 文字列JSONなら辞書/配列へ
    - 配列なら date/target_date が date_str に一致する要素を優先
    - 無ければ先頭、無ければ {}
    """
    core = _unwrap_meal_container(meal_with_basis)

    if isinstance(core, list):
        if not core:
            return {}
        target = _date_key(date_str)
        for obj in core:
            day = _date_key(str(obj.get("date", "")))
            if day == target:
                return obj
        for obj in core:
            day = _date_key(str(obj.get("target_date", "")))
            if day == target:
                return obj
        return core[0]

    if isinstance(core, dict):
        return core or {}

    # 想定外は空
    return {}

def format_daily_report(
    meal_with_basis: Any,
    anthropometric: Any,
    date_str: str
) -> str:
    # 0) 正規化
    meal_obj = _select_meal_object(meal_with_basis, date_str)
    anth_obj = _normalize_anthropometric(anthropometric)

    # 1) ヘッダー日付
    date_line = _parse_date(date_str)

    # 2) 体組成
    anth = _pick_anthro_for_date(anth_obj, date_str)
    w = _fmt_num(anth.get("weight"), "kg", 1)
    f = _fmt_num(anth.get("fat"), "%", 1)

    # 3) 目標
    basis = _get_basis(meal_obj)
    bcal = _fmt_num(basis.get("calorie"), " kcal", 0)
    bp = _fmt_num(basis.get("protein"), " g", 1)
    bf = _fmt_num(basis.get("fat"), " g", 1)
    bc = _fmt_num(basis.get("carbohydrate"), " g", 1)

    # 4) 食事履歴
    meals = _collect_meals(meal_obj)

    # 5) 合計
    sm = _get_summary(meal_obj)
    scal = _fmt_num(sm.get("calorie"), " kcal", 0)
    sp = _fmt_num(sm.get("protein"), " g", 1)
    sf = _fmt_num(sm.get("fat"), " g", 1)
    sc = _fmt_num(sm.get("carbohydrate"), " g", 1)

    # 本文生成
    lines: List[str] = []
    lines.append(f"📅 日付：{date_line}\n")
    lines.append("🧍‍♂️ 体組成（anthropometric）")
    lines.append(f"体重：{w}")
    lines.append(f"体脂肪率：{f}\n")

    lines.append("🎯 栄養目標（basis.all）")
    lines.append(f"カロリー：{bcal}")
    lines.append(f"たんぱく質：{bp}")
    lines.append(f"脂質：{bf}")
    lines.append(f"炭水化物：{bc}\n")

    lines.append("🍱 食事内容（meal_histories）")
    for key in MEAL_ORDER:
        label = MEAL_LABEL[key]
        lines.append(f"【{label}】")
        items = meals.get(key) or []
        if not items:
            lines.append("食事記録なし\n")
            continue
        for it in items:
            time = (it.get("time") or "").strip() or "--:--"
            name = (it.get("name") or "").strip() or "(名称未設定)"
            kcal = _fmt_num(it.get("calorie"), " kcal", 0)
            p = _fmt_num(it.get("protein"), "g", 1)
            fat = _fmt_num(it.get("fat"), "g", 1)
            c = _fmt_num(it.get("carbohydrate"), "g", 1)
            has_img = "✅" if (it.get("image_url") or "").strip() else ""
            lines.append(f"{time}　{name}　{kcal}　P:{p}　F:{fat}　C:{c}　{has_img}")
        lines.append("")  # 改行

    lines.append("📊 栄養摂取合計（meal_histories_summary.all）")
    lines.append(f"カロリー：{scal}")
    lines.append(f"たんぱく質：{sp}")
    lines.append(f"脂質：{sf}")
    lines.append(f"炭水化物：{sc}\n")

    return "\n".join(lines)
