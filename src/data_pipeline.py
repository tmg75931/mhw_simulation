"""
몬스터헌터 와일즈(MH Wilds) 데이터 파이프라인 모듈
- 외부 API (https://wilds.mhdb.io/{locale}) 데이터 호출 (requests)
- Streamlit @st.cache_data 인메모리 캐싱
- 방어구(Armor), 방어구 세트(Armor Sets), 스킬(Skills) DataFrame 전처리
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import pandas as pd
import requests
import streamlit as st

BASE_URL = "https://wilds.mhdb.io"

PART_KR_MAP: Dict[str, str] = {
    "head": "머리",
    "chest": "가슴",
    "arms": "팔",
    "waist": "허리",
    "legs": "다리",
}

RANK_KR_MAP: Dict[str, str] = {
    "low": "하위",
    "high": "상위",
    "master": "마스터",
}

SKILL_KIND_KR_MAP: Dict[str, str] = {
    "armor": "방어구 스킬",
    "weapon": "무기 스킬",
    "group": "그룹 스킬",
    "set": "시리즈 스킬",
}

RESISTANCE_MAP: Dict[str, str] = {
    "res_fire": "불 내성",
    "res_water": "물 내성",
    "res_thunder": "번개 내성",
    "res_ice": "얼음 내성",
    "res_dragon": "용 내성",
}


def _build_url(endpoint: str, locale: str = "ko") -> str:
    clean_ep = endpoint.lstrip("/")
    return f"{BASE_URL}/{locale}/{clean_ep}"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_raw_data(endpoint: str, locale: str = "ko") -> List[Dict[str, Any]]:
    """지정된 엔드포인트에서 JSON 리스트 데이터를 가져와 메모리에 캐싱합니다."""
    url = _build_url(endpoint, locale=locale)
    resp = requests.get(url, headers={"Accept": "application/json"}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


@st.cache_data(ttl=3600, show_spinner=False)
def load_skills_dataframe(locale: str = "ko") -> Tuple[pd.DataFrame, Dict[str, Dict[str, Any]]]:
    """스킬(/skills) 데이터를 호출하여 DataFrame과 스킬 사전으로 반환합니다."""
    raw_skills = fetch_raw_data("skills", locale=locale)
    rows: List[Dict[str, Any]] = []
    skill_lookup: Dict[str, Dict[str, Any]] = {}

    for s in raw_skills:
        skill_id = s.get("id")
        name = s.get("name") or f"Skill #{skill_id}"
        kind = s.get("kind", "armor")
        kind_kr = SKILL_KIND_KR_MAP.get(kind, kind)
        desc = s.get("description") or "-"
        ranks = s.get("ranks") or []
        max_level = max((r.get("level", 1) for r in ranks), default=1)

        rank_descriptions = {
            r.get("level", 1): (r.get("description") or "")
            for r in ranks
        }

        skill_info = {
            "id": skill_id,
            "name": name,
            "kind": kind,
            "kind_kr": kind_kr,
            "description": desc,
            "max_level": max_level,
            "rank_descriptions": rank_descriptions,
        }
        skill_lookup[name] = skill_info
        rows.append(
            {
                "스킬명": name,
                "분류": kind_kr,
                "최대 레벨": f"Lv.{max_level}",
                "스킬 설명": desc,
            }
        )

    return pd.DataFrame(rows), skill_lookup


@st.cache_data(ttl=3600, show_spinner=False)
def load_armor_sets_dataframe(locale: str = "ko") -> pd.DataFrame:
    """방어구 세트(/armor/sets) 데이터를 호출하여 DataFrame으로 변환합니다."""
    raw_sets = fetch_raw_data("armor/sets", locale=locale)
    rows: List[Dict[str, Any]] = []

    for aset in raw_sets:
        pieces = aset.get("pieces") or []
        piece_map = {p.get("kind"): p.get("name") for p in pieces if p.get("kind")}
        bonus_name = (aset.get("bonus") or {}).get("skill", {}).get("name")
        group_bonus_name = (aset.get("groupBonus") or {}).get("skill", {}).get("name")

        rows.append(
            {
                "set_id": aset.get("id"),
                "세트명": aset.get("name") or f"Set #{aset.get('id')}",
                "파츠 수": len(pieces),
                "시리즈 스킬": bonus_name or "-",
                "그룹 스킬": group_bonus_name or "-",
                "head": piece_map.get("head") or "-",
                "chest": piece_map.get("chest") or "-",
                "arms": piece_map.get("arms") or "-",
                "waist": piece_map.get("waist") or "-",
                "legs": piece_map.get("legs") or "-",
            }
        )

    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def load_armor_dataframe(locale: str = "ko") -> pd.DataFrame:
    """방어구(/armor) 데이터를 호출하여 분석 및 시각화에 최적화된 DataFrame으로 전처리합니다."""
    raw_armor = fetch_raw_data("armor", locale=locale)
    rows: List[Dict[str, Any]] = []

    for item in raw_armor:
        armor_id = item.get("id")
        name = item.get("name") or f"Armor #{armor_id}"
        kind = item.get("kind") or "head"
        part_kr = PART_KR_MAP.get(kind, kind)
        rank = item.get("rank") or "low"
        rank_kr = RANK_KR_MAP.get(rank, rank)
        rarity = int(item.get("rarity") or 1)

        defense_obj = item.get("defense") or {}
        def_base = int(defense_obj.get("base") or 0)
        def_max = int(defense_obj.get("max") or def_base)

        res_obj = item.get("resistances") or {}
        res_fire = int(res_obj.get("fire") or 0)
        res_water = int(res_obj.get("water") or 0)
        res_thunder = int(res_obj.get("thunder") or 0)
        res_ice = int(res_obj.get("ice") or 0)
        res_dragon = int(res_obj.get("dragon") or 0)
        res_total = res_fire + res_water + res_thunder + res_ice + res_dragon

        slots = item.get("slots") or []
        slots_str = " ".join(f"[{s}]" for s in slots) if slots else "-"
        slot_score = sum(int(s) for s in slots if isinstance(s, (int, float)))

        skills_raw = item.get("skills") or []
        skills_dict: Dict[str, int] = {}
        skills_list_str: List[str] = []

        for sk_entry in skills_raw:
            sk_obj = sk_entry.get("skill") or {}
            sk_name = sk_obj.get("name") or sk_entry.get("name")
            sk_lv = int(sk_entry.get("level") or 1)
            if sk_name:
                skills_dict[sk_name] = skills_dict.get(sk_name, 0) + sk_lv
                skills_list_str.append(f"{sk_name} Lv.{sk_lv}")

        skills_summary = ", ".join(skills_list_str) if skills_list_str else "-"
        skill_level_sum = sum(skills_dict.values())
        efficiency_score = skill_level_sum + slot_score
        armor_set_name = (item.get("armorSet") or {}).get("name") or "-"

        rows.append(
            {
                "id": armor_id,
                "name": name,
                "kind": kind,
                "part_kr": part_kr,
                "rank": rank,
                "rank_kr": rank_kr,
                "rarity": rarity,
                "armor_set": armor_set_name,
                "defense_base": def_base,
                "defense_max": def_max,
                "res_fire": res_fire,
                "res_water": res_water,
                "res_thunder": res_thunder,
                "res_ice": res_ice,
                "res_dragon": res_dragon,
                "res_total": res_total,
                "slots": slots,
                "slots_str": slots_str,
                "slot_score": slot_score,
                "skills_dict": skills_dict,
                "skills_summary": skills_summary,
                "skill_level_sum": skill_level_sum,
                "efficiency_score": efficiency_score,
                "description": item.get("description") or "",
            }
        )

    return pd.DataFrame(rows)


def calculate_custom_set_stats(
    selected_rows: List[pd.Series],
    skill_lookup: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """선택된 5부위 방어구의 종합 물리 방어력, 5대 속성 내성, 발동 스킬 레벨을 합산합니다."""
    total_def_base = 0
    total_def_max = 0
    resistances = {
        "불": 0,
        "물": 0,
        "번개": 0,
        "얼음": 0,
        "용": 0,
    }
    aggregated_skills: Dict[str, int] = {}
    skill_sources: Dict[str, List[str]] = {}
    total_slots: List[int] = []

    for row in selected_rows:
        if row is None or row.empty:
            continue
        total_def_base += int(row["defense_base"])
        total_def_max += int(row["defense_max"])
        resistances["불"] += int(row["res_fire"])
        resistances["물"] += int(row["res_water"])
        resistances["번개"] += int(row["res_thunder"])
        resistances["얼음"] += int(row["res_ice"])
        resistances["용"] += int(row["res_dragon"])

        if isinstance(row["slots"], list):
            total_slots.extend(row["slots"])

        sk_dict: Dict[str, int] = row["skills_dict"] or {}
        for sk_name, lv in sk_dict.items():
            aggregated_skills[sk_name] = aggregated_skills.get(sk_name, 0) + lv
            skill_sources.setdefault(sk_name, []).append(f"{row['part_kr']}(+{lv})")

    skill_rows: List[Dict[str, Any]] = []
    for sk_name, total_lv in sorted(
        aggregated_skills.items(), key=lambda x: (-x[1], x[0])
    ):
        meta = skill_lookup.get(sk_name, {})
        sk_kind = meta.get("kind", "armor")
        max_lv = meta.get("max_level", 7)
        effective_lv = min(total_lv, max_lv)
        overflow_lv = max(0, total_lv - max_lv)
        rank_descs = meta.get("rank_descriptions", {})
        effect_text = rank_descs.get(effective_lv) or meta.get("description") or "-"

        if sk_kind == "group":
            is_active = total_lv >= 3
            lv_label = f"발동 ({total_lv}/3파츠)" if is_active else f"미발동 ({total_lv}/3파츠)"
        else:
            lv_label = f"Lv.{effective_lv} / {max_lv}"

        skill_rows.append(
            {
                "스킬명": sk_name,
                "분류": meta.get("kind_kr", "방어구 스킬"),
                "합산 레벨": total_lv,
                "유효 레벨": effective_lv,
                "최대 레벨": max_lv,
                "초과 레벨": overflow_lv if sk_kind != "group" else 0,
                "레벨 표기": lv_label,
                "발동 효과": effect_text,
                "기여 부위": ", ".join(skill_sources.get(sk_name, [])),
            }
        )

    skills_df = pd.DataFrame(skill_rows)

    slot_summary = {
        3: total_slots.count(3),
        2: total_slots.count(2),
        1: total_slots.count(1),
    }

    return {
        "total_def_base": total_def_base,
        "total_def_max": total_def_max,
        "resistances": resistances,
        "skills_df": skills_df,
        "slot_summary": slot_summary,
    }
