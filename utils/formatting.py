# utils/formatting.py
from datetime import datetime
from typing import Dict, Any, Optional, List

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
    """
    入力例:
      - '2025-08-07'
      - '2025/08/07'
      - '2025-08-07T00:00:00+09:00'
    出力: '2025/08/07'
    """
    if not date_str:
        return ""
    core = date_str[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(core, fmt).strftime("%Y/%m/%d")
        except ValueError:
            continue
    # ダメならそのまま返す
    return date_str

def _date_key(s: str) -> str:
    """比較用に 'YYYY-MM-DD' へ正規化"""
    if not s:
        return ""
    core = s[:10].replace("/", "-")
    return core

def _pick_anthro_for_date(anthro_json: Dict[str, Any], date_str: str) -> Dict[str, Optional[float]]:
    """
    anthropometric 側は通常:
    { "data": [ {"date":"2025-08-07","weight":65.4,"fat":17.7}, ... ] }
    だが、配列そのものが返る場合もあるため normalize 済みを想定。
    """
    items = (anthro_json or {}).get("data") or []
    target = _date_key(date_str)
    for row in items:
        rdate = _date_key(str(row.get("date", "")))
        if rdate == target:
            return {"weight": row.get("weight"), "fat": row.get("fat")}
    # 見つからなければ None
    return {"weight": None, "fat": None}

def _collect_meals(meal_with_basis: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    meal_with_basis から meal_histories を取り出し、種類別にグループ化。
    期待形:
      meal_with_basis["meal_histories"] = [
        {"meal_type":"morning","time":"08:00","name":"玄米ごはん",
         "calorie":260,"protein":5.3,"fat":2.1,"carbohydrate":56.4,"image_url": "..."},
        ...
      ]
    """
    grouped = {k: [] for k in MEAL_ORDER}
    for item in (meal_with_basis or {}).get("meal_histories", []) or []:
        mtype = (item.get("meal_type") or "").strip()
        if mtype in grouped:
            grouped[mtype].append(item)
    return grouped

def _get_basis(meal_with_basis: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    basis.all を想定:
      meal_with_basis["basis"]["all"] = {calorie, protein, fat, carbohydrate}
    """
    allv = ((meal_with_basis or {}).get("basis") or {}).get("all") or {}
    return {
        "calorie": allv.get("calorie"),
        "protein": allv.get("protein"),
        "fat": allv.get("fat"),
        "carbohydrate": allv.get("carbohydrate"),
    }

def _get_summary(meal_with_basis: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    meal_histories_summary.all を想定:
      meal_with_basis["meal_histories_summary"]["all"] = {calorie, protein, fat, carbohydrate}
    """
    allv = ((meal_with_basis or {}).get("meal_histories_summary") or {}).get("all") or {}
    return {
        "calorie": allv.get("calorie"),
        "protein": allv.get("protein"),
        "fat": allv.get("fat"),
        "carbohydrate": allv.get("carbohydrate"),
    }

def _normalize_anthropometric(anthropometric: Any) -> Dict[str, Any]:
    """
    anthropometric が配列で返る場合に {"data": [...]} へ正規化。
    それ以外はそのまま返す。
    """
    if isinstance(anthropometric, list):
        return {"data": anthropometric}
    return anthropometric or {}

def _select_meal_object(meal_with_basis: Any, date_str: str) -> Dict[str, Any]:
    """
    meal_with_basis が配列の場合、対象日(date_str)に一致する要素を選択。
    一致キーは 'date' or 'target_date' を優先して探す。
    一致が無ければ先頭要素、空なら {}。
    辞書ならそのまま返す。
    """
    if isinstance(meal_with_basis, list):
        if not meal_with_basis:
            return {}
        target = _date_key(date_str)
        # まず date で厳密一致
        for obj in meal_with_basis:
            day = _date_key(str(obj.get("date", "")))
            if day == target:
                return obj
        # 次に target_date でも一致を試す
        for obj in meal_with_basis:
            day = _date_key(str(obj.get("target_date", "")))
            if day == target:
                return obj
        # 見つからなければ先頭
        return meal_with_basis[0]
    return meal_with_basis or {}

def format_daily_report(
    meal_with_basis: Any,
    anthropometric: Any,
    date_str: str
) -> str:
    """
    入力:
      - meal_with_basis: /meal_with_basis のJSON（辞書 or 日別配列）
      - anthropometric : /anthropometric のJSON（辞書 or 配列）
      - date_str       : 'YYYY-MM-DD' or 'YYYY/MM/DD' or ISO8601
    出力:
      - 指定フォーマットのテキスト
    """
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
