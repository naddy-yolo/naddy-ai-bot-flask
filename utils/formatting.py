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
    受け取り想定：
      - '2025-08-07'
      - '2025/08/07'
      - '2025-08-07T00:00:00+09:00'
    出力：'2025/08/07'
    """
    if not date_str:
        return ""
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").strftime("%Y/%m/%d")
    except ValueError:
        try:
            return datetime.strptime(date_str[:10], "%Y/%m/%d").strftime("%Y/%m/%d")
        except ValueError:
            return date_str

def _pick_anthro_for_date(anthro_json: Dict[str, Any], date_str: str) -> Dict[str, Optional[float]]:
    """
    anthropometric 側は日付配列を想定：
    {
      "data": [
        {"date": "2025-08-07", "weight": 65.4, "fat": 17.7},
        ...
      ]
    }
    """
    items = (anthro_json or {}).get("data") or []
    date_key = date_str[:10].replace("/", "-")
    for row in items:
        rdate = (row.get("date") or "")[:10]
        if rdate == date_key:
            return {
                "weight": row.get("weight"),
                "fat": row.get("fat"),
            }
    return {"weight": None, "fat": None}

def _collect_meals(meal_with_basis: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    meal_histories 配列を想定：
    {
      "meal_histories": [
        {
          "meal_type": "morning" | "noon" | "night" | "snack",
          "time": "08:00",
          "name": "玄米ごはん",
          "calorie": 260.0,
          "protein": 5.3,
          "fat": 2.1,
          "carbohydrate": 56.4,
          "image_url": "https://..."  # 無ければ None
        },
        ...
      ]
    }
    """
    grouped = {k: [] for k in MEAL_ORDER}
    for item in (meal_with_basis or {}).get("meal_histories", []) or []:
        mtype = (item.get("meal_type") or "").strip()
        if mtype in grouped:
            grouped[mtype].append(item)
    return grouped

def _get_basis(meal_with_basis: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    basis.all を想定：
    {
      "basis": {
        "all": {
          "calorie": 1800,
          "protein": 157.5,
          "fat": 40,
          "carbohydrate": 202.5
        }
      }
    }
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
    meal_histories_summary.all を想定：
    {
      "meal_histories_summary": {
        "all": {
          "calorie": 829,
          "protein": 63.7,
          "fat": 15.5,
          "carbohydrate": 113.4
        }
      }
    }
    """
    allv = ((meal_with_basis or {}).get("meal_histories_summary") or {}).get("all") or {}
    return {
        "calorie": allv.get("calorie"),
        "protein": allv.get("protein"),
        "fat": allv.get("fat"),
        "carbohydrate": allv.get("carbohydrate"),
    }

def format_daily_report(
    meal_with_basis: Dict[str, Any],
    anthropometric: Dict[str, Any],
    date_str: str
) -> str:
    """
    入力：
      - meal_with_basis: Calomeal /meal_with_basis のJSON
      - anthropometric:  Calomeal /anthropometric のJSON
      - date_str:        '2025-08-07' など（API取得日 or 画面の対象日）
    出力：
      - 指定フォーマットのテキスト
    """
    # 1) ヘッダー日付
    date_line = _parse_date(date_str)

    # 2) 体組成
    anth = _pick_anthro_for_date(anthropometric, date_str)
    w = _fmt_num(anth.get("weight"), "kg", 1)
    f = _fmt_num(anth.get("fat"), "%", 1)

    # 3) 目標
    basis = _get_basis(meal_with_basis)
    bcal = _fmt_num(basis.get("calorie"), " kcal", 0)
    bp = _fmt_num(basis.get("protein"), " g", 1)
    bf = _fmt_num(basis.get("fat"), " g", 1)
    bc = _fmt_num(basis.get("carbohydrate"), " g", 1)

    # 4) 食事履歴
    meals = _collect_meals(meal_with_basis)

    # 5) 合計
    sm = _get_summary(meal_with_basis)
    scal = _fmt_num(sm.get("calorie"), " kcal", 0)
    sp = _fmt_num(sm.get("protein"), " g", 1)
    sf = _fmt_num(sm.get("fat"), " g", 1)
    sc = _fmt_num(sm.get("carbohydrate"), " g", 1)

    # 本文生成
    lines = []
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
