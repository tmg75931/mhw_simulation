"""
몬스터헌터 와일즈(MH Wilds) 데이터 파이프라인 모듈 (고속 최적화 버전)
- 로컬 압축 스냅샷(data/mh_wilds_ko_cache.json.gz) 즉시 프리로드 + ThreadPoolExecutor 병렬 API 동기화
- Streamlit @st.cache_data(ttl=86400) 인메모리 캐싱 및 O(1) 사전 인덱싱 조회 테이블 제공
- 방어구(Armor), 방어구 세트(Armor Sets), 스킬(Skills), 장식주(Decorations) DataFrame 전처리
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple, Union
import pandas as pd
import requests
import streamlit as st

BASE_URL = "https://wilds.mhdb.io"
ENDPOINTS = ("armor", "armor/sets", "skills", "decorations")
CACHE_FILE_PATH = Path(__file__).resolve().parent.parent / "data" / "mh_wilds_ko_cache.json.gz"

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


def sync_remote_snapshot(locale: str = "ko") -> Dict[str, List[Dict[str, Any]]]:
    """4개 엔드포인트를 병렬(ThreadPoolExecutor)로 동시에 호출하여 최신 데이터를 받아오고 로컬 캐시를 갱신합니다."""
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    def _fetch_one(ep: str) -> Tuple[str, List[Dict[str, Any]]]:
        url = _build_url(ep, locale=locale)
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return ep, (data if isinstance(data, list) else [])

    with ThreadPoolExecutor(max_workers=4) as executor:
        bundle = dict(executor.map(_fetch_one, ENDPOINTS))

    if locale == "ko":
        try:
            CACHE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(CACHE_FILE_PATH, "wt", encoding="utf-8") as f:
                json.dump(bundle, f, ensure_ascii=False)
        except OSError:
            pass

    return bundle


@st.cache_data(ttl=86400, show_spinner=False)
def load_raw_bundle(locale: str = "ko") -> Dict[str, List[Dict[str, Any]]]:
    """로컬 압축 스냅샷이 있으면 0.04초 만에 즉시 로드하고, 없으면 병렬 API 호출로 가져옵니다."""
    if locale == "ko" and CACHE_FILE_PATH.exists():
        try:
            with gzip.open(CACHE_FILE_PATH, "rt", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and all(ep in data for ep in ENDPOINTS):
                return data
        except (OSError, json.JSONDecodeError):
            pass

    return sync_remote_snapshot(locale=locale)


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_raw_data(endpoint: str, locale: str = "ko") -> List[Dict[str, Any]]:
    """지정된 엔드포인트에서 JSON 리스트 데이터를 가져와 메모리에 캐싱합니다."""
    clean_ep = endpoint.lstrip("/")
    bundle = load_raw_bundle(locale=locale)
    if clean_ep in bundle:
        return bundle[clean_ep]

    url = _build_url(clean_ep, locale=locale)
    resp = requests.get(url, headers={"Accept": "application/json"}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


@st.cache_data(ttl=86400, show_spinner=False)
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


@st.cache_data(ttl=86400, show_spinner=False)
def load_decorations_dataframe(locale: str = "ko") -> pd.DataFrame:
    """장식주(/decorations) 데이터를 호출하여 DataFrame으로 변환합니다."""
    raw_decos = fetch_raw_data("decorations", locale=locale)
    rows: List[Dict[str, Any]] = []

    for d in raw_decos:
        deco_id = d.get("id")
        name = d.get("name") or f"Decoration #{deco_id}"
        slot = int(d.get("slot") or 1)
        rarity = int(d.get("rarity") or 1)
        kind = d.get("kind") or "armor"
        kind_kr = "방어구용" if kind == "armor" else "무기용"

        skills_raw = d.get("skills") or []
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
        display_label = f"{name} · {skills_summary}"

        rows.append(
            {
                "id": deco_id,
                "name": name,
                "kind": kind,
                "kind_kr": kind_kr,
                "slot": slot,
                "rarity": rarity,
                "skills_dict": skills_dict,
                "skills_summary": skills_summary,
                "display_label": display_label,
                "description": d.get("description") or "",
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=["slot", "rarity", "name"], ascending=[False, False, True]).reset_index(drop=True)
    return df


@st.cache_data(ttl=86400, show_spinner=False)
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


@st.cache_data(ttl=86400, show_spinner=False)
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
        display_label = f"{name} (방어 {def_base} · R{rarity})"

        rows.append(
            {
                "id": armor_id,
                "name": name,
                "display_label": display_label,
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
                "search_blob": f"{name} {armor_set_name} {skills_summary}".lower(),
            }
        )

    return pd.DataFrame(rows)


@st.cache_data(ttl=86400, show_spinner=False)
def build_simulator_lookup_tables(locale: str = "ko") -> Dict[str, Any]:
    """
    시뮬레이터 렌더링 시 매번 발생하던 O(N) DataFrame 필터링을 제거하기 위해
    부위별 방어구 옵션, O(1) 해시맵(name -> dict, name -> label), 슬롯 레벨별 장식주 목록을 사전 생성합니다.
    """
    armor_df = load_armor_dataframe(locale)
    armor_sets_df = load_armor_sets_dataframe(locale)
    decorations_df = load_decorations_dataframe(locale)
    armor_decos_df = decorations_df[decorations_df["kind"] == "armor"].reset_index(drop=True)

    part_options: Dict[str, List[str]] = {}
    part_label_map: Dict[str, Dict[str, str]] = {}
    part_row_map: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for p_key in PART_KR_MAP:
        sub_df = armor_df[armor_df["kind"] == p_key].sort_values(
            by=["rarity", "defense_base", "name"], ascending=[False, False, True]
        )
        records = sub_df.to_dict("records")
        names = ["(장착 안 함)"] + [r["name"] for r in records]
        labels = {"(장착 안 함)": "(장착 안 함)"}
        row_map: Dict[str, Dict[str, Any]] = {}
        for r in records:
            labels[r["name"]] = r["display_label"]
            row_map[r["name"]] = r

        part_options[p_key] = names
        part_label_map[p_key] = labels
        part_row_map[p_key] = row_map

    # 프리셋 O(1) 조회 사전
    valid_sets_df = armor_sets_df[armor_sets_df["파츠 수"] == 5]
    preset_names = valid_sets_df["세트명"].tolist()
    preset_map = {r["세트명"]: r for r in valid_sets_df.to_dict("records")}

    # 슬롯 레벨(1, 2, 3)별 호환 방어구 장식주 옵션 & O(1) 조회 사전
    deco_records = armor_decos_df.to_dict("records")
    deco_by_label: Dict[str, Dict[str, Any]] = {r["display_label"]: r for r in deco_records}
    deco_options_by_slot: Dict[int, List[str]] = {}
    for slot_lv in (1, 2, 3):
        deco_options_by_slot[slot_lv] = ["(비어 있음)"] + [
            r["display_label"] for r in deco_records if int(r["slot"]) <= slot_lv
        ]

    return {
        "part_options": part_options,
        "part_label_map": part_label_map,
        "part_row_map": part_row_map,
        "preset_names": preset_names,
        "preset_map": preset_map,
        "deco_by_label": deco_by_label,
        "deco_options_by_slot": deco_options_by_slot,
    }


RowLike = Union[pd.Series, Mapping[str, Any]]


def calculate_custom_set_stats(
    selected_rows: List[RowLike],
    skill_lookup: Dict[str, Dict[str, Any]],
    equipped_decorations: List[Tuple[str, RowLike]] | None = None,
) -> Dict[str, Any]:
    """
    선택된 5부위 방어구 및 장착된 장식주의 종합 물리 방어력, 5대 속성 내성, 발동 스킬 레벨을 합산합니다.
    equipped_decorations: [(부위명, 장식주 dict 또는 Series), ...]
    """
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
    armor_skill_lv: Dict[str, int] = {}
    deco_skill_lv: Dict[str, int] = {}
    skill_sources: Dict[str, List[str]] = {}
    total_slots: List[int] = []

    # 1. 방어구 5부위 스탯 및 스킬 합산
    for row in selected_rows:
        if row is None or (isinstance(row, pd.Series) and row.empty):
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
            armor_skill_lv[sk_name] = armor_skill_lv.get(sk_name, 0) + lv
            skill_sources.setdefault(sk_name, []).append(f"{row['part_kr']}(+{lv})")

    # 2. 장착된 장식주 스킬 합산
    equipped_deco_count = 0
    if equipped_decorations:
        for part_kr, deco_row in equipped_decorations:
            if deco_row is None or (isinstance(deco_row, pd.Series) and deco_row.empty):
                continue
            equipped_deco_count += 1
            d_sk_dict: Dict[str, int] = deco_row["skills_dict"] or {}
            for sk_name, lv in d_sk_dict.items():
                aggregated_skills[sk_name] = aggregated_skills.get(sk_name, 0) + lv
                deco_skill_lv[sk_name] = deco_skill_lv.get(sk_name, 0) + lv
                skill_sources.setdefault(sk_name, []).append(
                    f"💎{part_kr}:{deco_row['name']}(+{lv})"
                )

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

        from_armor = armor_skill_lv.get(sk_name, 0)
        from_deco = deco_skill_lv.get(sk_name, 0)

        if sk_kind == "group":
            is_active = total_lv >= 3
            lv_label = f"발동 ({total_lv}/3파츠)" if is_active else f"미발동 ({total_lv}/3파츠)"
        else:
            lv_label = f"Lv.{effective_lv} / {max_lv}"
            if from_deco > 0:
                lv_label += f" (장식주 +{from_deco})"

        skill_rows.append(
            {
                "스킬명": sk_name,
                "분류": meta.get("kind_kr", "방어구 스킬"),
                "합산 레벨": total_lv,
                "유효 레벨": effective_lv,
                "방어구 레벨": min(from_armor, effective_lv),
                "장식주 레벨": max(0, effective_lv - min(from_armor, effective_lv)),
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
        "total": len(total_slots),
        "equipped": equipped_deco_count,
    }

    return {
        "total_def_base": total_def_base,
        "total_def_max": total_def_max,
        "resistances": resistances,
        "skills_df": skills_df,
        "slot_summary": slot_summary,
    }
