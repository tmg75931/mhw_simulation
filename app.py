"""
몬스터헌터 와일즈(Monster Hunter Wilds) 장비 & 스탯 대시보드 (고속 최적화 버전)
- 테마: 금지된 땅 조사단 길드 아카이브 (Warm Sand, Parchment & Antique Gold/Bronze)
- 최적화: 로컬 압축 스냅샷 프리로드 + O(1) 사전 해시맵 인덱싱 + @st.fragment 부분 렌더링
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data_pipeline import (
    PART_KR_MAP,
    RANK_KR_MAP,
    build_simulator_lookup_tables,
    calculate_custom_set_stats,
    load_armor_dataframe,
    load_armor_sets_dataframe,
    load_decorations_dataframe,
    load_skills_dataframe,
    sync_remote_snapshot,
)

# ============================================================================
# 페이지 기본 설정
# ============================================================================
st.set_page_config(
    page_title="몬스터헌터 와일즈 길드 장비 공방",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# 몬스터헌터 와일즈(Forbidden Lands / Hunter's Guild Note) 테마 스타일링
# ============================================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=Noto+Serif+KR:wght@600;700;900&display=swap');

    /* 전체 배경: 금지된 땅의 따뜻한 사막 모래 & 양피지 톤 */
    .stApp {
        background-color: #f4efe6;
        background-image: radial-gradient(circle at 50% 0%, #faf6ef 0%, #f1eadc 70%, #e9dfc9 100%);
        color: #2b2118;
    }
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3rem;
        max-width: 1460px;
    }

    /* 사이드바: 헌터 길드 양피지 패널 */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ebe2d1 0%, #e2d6c1 100%);
        border-right: 2px solid #c8b496;
    }
    .guild-sidebar-header {
        border-bottom: 2px solid #b47b22;
        padding-bottom: 10px;
        margin-bottom: 12px;
    }
    .guild-sidebar-header .en-sub {
        font-family: 'Cinzel', serif;
        font-size: 0.72rem;
        letter-spacing: 0.14em;
        color: #8c5e18;
        font-weight: 700;
    }
    .guild-sidebar-header h3 {
        font-family: 'Noto Serif KR', serif;
        font-size: 1.2rem;
        font-weight: 900;
        color: #2b2118;
        margin: 2px 0 0 0;
    }

    /* 상단 히어로 배너: 몬스터헌터 와일즈 가죽 & 황금 문장 스타일 */
    .wilds-hero-banner {
        background: linear-gradient(135deg, #261c14 0%, #3d2d1e 50%, #221810 100%);
        border: 2px solid #c59b27;
        border-radius: 12px;
        padding: 20px 28px;
        margin-bottom: 1.3rem;
        box-shadow: 0 6px 20px rgba(43, 33, 24, 0.18), inset 0 0 0 1px rgba(243, 210, 102, 0.22);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 18px;
        position: relative;
        overflow: hidden;
    }
    .wilds-hero-left {
        display: flex;
        align-items: center;
        gap: 18px;
    }
    .wilds-emblem {
        width: 58px;
        height: 58px;
        border-radius: 50%;
        background: radial-gradient(circle, #3d2d1e 0%, #1d150e 100%);
        border: 2px solid #d4af37;
        box-shadow: 0 0 12px rgba(212, 175, 55, 0.35);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .wilds-title-group .en-label {
        font-family: 'Cinzel', serif;
        font-size: 0.76rem;
        letter-spacing: 0.2em;
        color: #e5c158;
        font-weight: 700;
        margin-bottom: 3px;
    }
    .wilds-title-group h1 {
        font-family: 'Noto Serif KR', serif;
        font-size: 1.6rem;
        font-weight: 900;
        color: #fdf8ed;
        margin: 0;
        letter-spacing: -0.01em;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.45);
    }
    .wilds-title-group p {
        font-size: 0.88rem;
        color: #d6c7b2;
        margin: 4px 0 0 0;
    }
    .wilds-badge-right {
        font-family: 'Cinzel', serif;
        font-size: 0.78rem;
        color: #e5c158;
        border: 1px solid rgba(229, 193, 88, 0.45);
        background: rgba(0, 0, 0, 0.25);
        padding: 6px 14px;
        border-radius: 6px;
        letter-spacing: 0.08em;
        white-space: nowrap;
    }

    /* 위젯 라벨 한 줄 고정 */
    div[data-testid="stWidgetLabel"] p {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        font-weight: 700 !important;
        font-size: 0.83rem !important;
        color: #4a3723 !important;
    }

    /* 입력창 및 셀렉트박스 양피지 톤 매칭 */
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {
        background-color: #fffdf9 !important;
        border-color: #cbb89d !important;
    }

    /* 메트릭 카드: 양피지 카드 + 황동/골드 포인트 보더 */
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, #fffdf9 0%, #f9f4ea 100%);
        border: 1px solid #d5c4aa;
        border-left: 5px solid #b47b22;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 2px 6px rgba(58, 42, 24, 0.06);
        min-height: 88px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    div[data-testid="stMetricLabel"] p {
        font-size: 0.82rem !important;
        font-weight: 700 !important;
        color: #785a37 !important;
        white-space: nowrap !important;
        overflow: visible !important;
    }
    div[data-testid="stMetricValue"] > div {
        font-family: 'Noto Serif KR', sans-serif !important;
        font-size: 1.32rem !important;
        font-weight: 900 !important;
        color: #2b2118 !important;
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }

    /* border=True 컨테이너: 길드 문서(양피지 카드) 디자인 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #fbf8f1;
        border: 1px solid #d5c4aa !important;
        border-top: 3px solid #b47b22 !important;
        border-radius: 10px !important;
        box-shadow: 0 3px 10px rgba(58, 42, 24, 0.06);
    }

    /* 탭 메뉴 디자인 */
    button[data-baseweb="tab"] {
        font-family: 'Noto Serif KR', sans-serif !important;
        font-size: 0.96rem !important;
        font-weight: 700 !important;
        color: #6e5536 !important;
        padding: 10px 20px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #8c580c !important;
        background-color: rgba(180, 123, 34, 0.08) !important;
        border-radius: 8px 8px 0 0 !important;
    }

    /* 시뮬레이터 파츠 카드 내부 */
    .part-card-title {
        font-family: 'Noto Serif KR', serif;
        font-size: 0.92rem;
        font-weight: 800;
        color: #3b2a18;
        margin-bottom: 6px;
        border-bottom: 1px dashed #d5c4aa;
        padding-bottom: 4px;
    }
    .part-info-box {
        background-color: #f3ece0;
        border: 1px solid #dccbb2;
        border-radius: 8px;
        padding: 8px 10px;
        margin-top: 4px;
        margin-bottom: 6px;
        min-height: 62px;
        font-size: 0.78rem;
        line-height: 1.45;
    }
    .part-info-meta {
        font-weight: 800;
        color: #8c580c;
        margin-bottom: 3px;
    }
    .part-info-skills {
        color: #3b2a18;
        word-break: keep-all;
    }
    .deco-slot-header {
        font-size: 0.76rem;
        font-weight: 700;
        color: #6e5536;
        margin: 6px 0 4px 0;
        padding-top: 4px;
        border-top: 1px dashed #dccbb2;
    }
    .no-slot-badge {
        font-size: 0.75rem;
        color: #9c886e;
        background: rgba(0, 0, 0, 0.03);
        border: 1px dashed #d5c4aa;
        border-radius: 6px;
        padding: 6px 8px;
        text-align: center;
        margin-top: 6px;
    }
    .section-title {
        font-family: 'Noto Serif KR', serif;
        font-size: 1.06rem;
        font-weight: 800;
        color: #2b2118;
        margin-bottom: 0.25rem;
    }
    .chart-caption {
        font-size: 0.8rem;
        color: #785a37;
        margin-bottom: 0.5rem;
    }

    /* =======================================================================
       📱 모바일 폰 맞춤 반응형 스타일 (화면 폭 768px 이하 스마트폰 최적화)
       ======================================================================= */
    @media (max-width: 768px) {
        .block-container {
            padding: 0.8rem 0.6rem 2rem !important;
        }
        .wilds-hero-banner {
            padding: 14px 16px !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 12px !important;
            border-radius: 10px !important;
            margin-bottom: 0.9rem !important;
        }
        .wilds-hero-left {
            gap: 12px !important;
        }
        .wilds-emblem {
            width: 44px !important;
            height: 44px !important;
        }
        .wilds-emblem svg {
            width: 24px !important;
            height: 24px !important;
        }
        .wilds-title-group .en-label {
            font-size: 0.68rem !important;
            letter-spacing: 0.12em !important;
        }
        .wilds-title-group h1 {
            font-size: 1.25rem !important;
            line-height: 1.3 !important;
        }
        .wilds-title-group p {
            font-size: 0.78rem !important;
            line-height: 1.35 !important;
        }
        .wilds-badge-right {
            display: inline-block !important;
            font-size: 0.7rem !important;
            padding: 3px 8px !important;
        }
        div[data-baseweb="tab-list"] {
            gap: 4px !important;
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
        }
        button[data-baseweb="tab"] {
            font-size: 0.86rem !important;
            padding: 8px 12px !important;
            white-space: nowrap !important;
        }
        div[data-testid="stMetric"] {
            min-height: 68px !important;
            padding: 8px 12px !important;
            border-left-width: 4px !important;
        }
        div[data-testid="stMetricLabel"] p {
            font-size: 0.76rem !important;
        }
        div[data-testid="stMetricValue"] > div {
            font-size: 1.15rem !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 8px !important;
        }
        .part-info-box {
            min-height: auto !important;
            padding: 6px 8px !important;
            font-size: 0.74rem !important;
            line-height: 1.35 !important;
        }
        .part-card-title {
            font-size: 0.85rem !important;
            padding-bottom: 2px !important;
        }
        .js-plotly-plot {
            margin: 0 auto !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.fragment
def render_simulator_tab(
    sim_tables: Dict[str, Any],
    skill_lookup: Dict[str, Dict[str, Any]],
) -> None:
    """탭 1: 5부위 방어구 + 부위별 장식주 장착 시뮬레이터 (@st.fragment 부분 렌더링 적용)"""
    part_options_map = sim_tables["part_options"]
    part_label_map = sim_tables["part_label_map"]
    part_row_map = sim_tables["part_row_map"]
    preset_names = sim_tables["preset_names"]
    preset_map = sim_tables["preset_map"]
    deco_by_label = sim_tables["deco_by_label"]
    deco_options_by_slot = sim_tables["deco_options_by_slot"]

    with st.container(border=True):
        top_bar1, top_bar2 = st.columns([1.8, 3.2])
        with top_bar1:
            preset_choice = st.selectbox(
                "⚡ 풀세트 프리셋 빠른 장착",
                options=["직접 커스텀 조합"] + preset_names,
                index=0,
            )
        with top_bar2:
            st.markdown(
                "<div style='padding-top: 26px; font-size: 0.88rem; color: #785a37;'>"
                "💡 각 부위의 방어구를 고르면 보유한 슬롯(【3】/【2】/【1】)에 맞는 <b>방어구 장식주</b>를 직접 장착해 스킬을 합산할 수 있습니다."
                "</div>",
                unsafe_allow_html=True,
            )

    preset_row = preset_map.get(preset_choice) if preset_choice != "직접 커스텀 조합" else None

    part_keys = ["head", "chest", "arms", "waist", "legs"]
    part_labels = {
        "head": "👑 머리 (Head)",
        "chest": "🦺 가슴 (Chest)",
        "arms": "🧤 팔 (Arms)",
        "waist": "🎗️ 허리 (Waist)",
        "legs": "🥾 다리 (Legs)",
    }

    selector_cols = st.columns(5, gap="small")
    selected_pieces: List[Dict[str, Any]] = []
    equipped_decorations: List[Tuple[str, Dict[str, Any]]] = []

    for idx, p_key in enumerate(part_keys):
        part_kr = PART_KR_MAP[p_key]
        options_list = part_options_map[p_key]
        label_lookup = part_label_map[p_key]
        row_lookup = part_row_map[p_key]

        default_idx = 1 if len(options_list) > 1 else 0
        if preset_row is not None:
            preset_piece_name = preset_row.get(p_key)
            if preset_piece_name in row_lookup:
                default_idx = options_list.index(preset_piece_name)

        with selector_cols[idx]:
            with st.container(border=True):
                st.markdown(
                    f'<div class="part-card-title">{part_labels[p_key]}</div>',
                    unsafe_allow_html=True,
                )
                chosen_name = st.selectbox(
                    part_labels[p_key],
                    options=options_list,
                    index=default_idx,
                    format_func=lambda nm, lk=label_lookup: lk.get(nm, nm),
                    label_visibility="collapsed",
                    key=f"builder_{p_key}_{preset_choice}",
                )
                if chosen_name != "(장착 안 함)" and chosen_name in row_lookup:
                    chosen_row = row_lookup[chosen_name]
                    selected_pieces.append(chosen_row)
                    st.markdown(
                        f"""
                        <div class="part-info-box">
                            <div class="part-info-meta">슬롯 {chosen_row['slots_str']} · 최대 {chosen_row['defense_max']}</div>
                            <div class="part-info-skills">{chosen_row['skills_summary']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    piece_slots = chosen_row["slots"] if isinstance(chosen_row["slots"], list) else []
                    if piece_slots:
                        st.markdown(
                            '<div class="deco-slot-header">💎 장식주 슬롯 장착</div>',
                            unsafe_allow_html=True,
                        )
                        for s_idx, slot_lv in enumerate(piece_slots):
                            slot_lv_int = max(1, min(3, int(slot_lv)))
                            deco_options = deco_options_by_slot[slot_lv_int]
                            selected_deco_label = st.selectbox(
                                f"슬롯 {s_idx + 1} 【{slot_lv}】",
                                options=deco_options,
                                index=0,
                                key=f"deco_{p_key}_{chosen_row['id']}_{s_idx}",
                            )
                            if selected_deco_label != "(비어 있음)" and selected_deco_label in deco_by_label:
                                equipped_decorations.append((part_kr, deco_by_label[selected_deco_label]))
                    else:
                        st.markdown(
                            '<div class="no-slot-badge">장식주 슬롯 없음</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        """
                        <div class="part-info-box">
                            <div class="part-info-meta" style="color:#9c886e;">미장착</div>
                            <div class="part-info-skills" style="color:#9c886e;">선택된 방어구 없음</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    sim_result = calculate_custom_set_stats(
        selected_pieces, skill_lookup, equipped_decorations=equipped_decorations
    )
    res_dict = sim_result["resistances"]
    slot_sum = sim_result["slot_summary"]
    active_skills_df = sim_result["skills_df"]

    stat_c1, stat_c2, stat_c3, stat_c4 = st.columns(4)
    stat_c1.metric("🛡️ 총합 기본 방어력", f"{sim_result['total_def_base']:,}")
    stat_c2.metric("✨ 총합 최대 강화 방어력", f"{sim_result['total_def_max']:,}")
    stat_c3.metric("🎯 총 발동 스킬 수", f"{len(active_skills_df)} 종")
    stat_c4.metric(
        "💎 장식주 장착 현황 (3 / 2 / 1슬롯)",
        f"{slot_sum['equipped']}/{slot_sum['total']}개 장착 ({slot_sum[3]}·{slot_sum[2]}·{slot_sum[1]})",
    )

    viz_col1, viz_col2 = st.columns([1.0, 1.2], gap="medium")

    with viz_col1:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">🕸️ 5대 속성 내성 밸런스</div>',
                unsafe_allow_html=True,
            )
            categories = [
                f"🔥 불 ({res_dict['불']:+d})",
                f"💧 물 ({res_dict['물']:+d})",
                f"⚡ 번개 ({res_dict['번개']:+d})",
                f"❄️ 얼음 ({res_dict['얼음']:+d})",
                f"🐉 용 ({res_dict['용']:+d})",
            ]
            values = list(res_dict.values())
            closed_categories = categories + [categories[0]]
            closed_values = values + [values[0]]

            min_r = min(min(values, default=0) - 6, -15)
            max_r = max(max(values, default=0) + 6, 20)

            fig_radar = go.Figure()
            fig_radar.add_trace(
                go.Scatterpolar(
                    r=closed_values,
                    theta=closed_categories,
                    fill="toself",
                    name="속성 내성 합계",
                    line=dict(color="#b47b22", width=3),
                    fillcolor="rgba(180, 123, 34, 0.25)",
                    marker=dict(size=8, color="#8c580c"),
                )
            )
            fig_radar.add_trace(
                go.Scatterpolar(
                    r=[0] * len(closed_categories),
                    theta=closed_categories,
                    mode="lines",
                    name="기준선 (0)",
                    line=dict(color="#a38f74", dash="dash", width=1.2),
                    hoverinfo="skip",
                )
            )
            fig_radar.update_layout(
                template="plotly_white",
                height=420,
                paper_bgcolor="#fbf8f1",
                font=dict(color="#2b2118", size=12),
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[min_r, max_r],
                        gridcolor="#dfd3c0",
                        tickfont=dict(size=11, color="#785a37"),
                    ),
                    angularaxis=dict(
                        gridcolor="#dfd3c0",
                        tickfont=dict(size=13, color="#2b2118"),
                    ),
                    bgcolor="#f4efe6",
                ),
                margin=dict(l=65, r=65, t=35, b=45),
                legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
            )
            st.plotly_chart(fig_radar, width="stretch")

    with viz_col2:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">📊 발동 스킬 레벨 현황 (방어구 + 장식주)</div>',
                unsafe_allow_html=True,
            )
            if active_skills_df.empty:
                st.info("장착된 방어구나 장식주에 발동 스킬이 없습니다.")
            else:
                plot_skills_df = active_skills_df.iloc[::-1].copy()
                max_x = max(
                    (plot_skills_df["유효 레벨"] + plot_skills_df["초과 레벨"]).max(),
                    5,
                )

                has_deco_lv = (plot_skills_df["장식주 레벨"] > 0).any()
                has_overflow = (plot_skills_df["초과 레벨"] > 0).any()

                fig_bar = go.Figure()
                fig_bar.add_trace(
                    go.Bar(
                        y=plot_skills_df["스킬명"],
                        x=plot_skills_df["방어구 레벨"],
                        orientation="h",
                        name="방어구 스킬",
                        marker=dict(color="#b47b22", cornerradius=4),
                        text=plot_skills_df["레벨 표기"] if not has_deco_lv else None,
                        textposition="outside" if not has_deco_lv else "none",
                        cliponaxis=False,
                        customdata=plot_skills_df[["발동 효과", "기여 부위", "레벨 표기"]],
                        hovertemplate=(
                            "<b>%{y}</b> (%{customdata[2]})<br>"
                            "효과: %{customdata[0]}<br>"
                            "기여: %{customdata[1]}<extra></extra>"
                        ),
                    )
                )
                if has_deco_lv:
                    fig_bar.add_trace(
                        go.Bar(
                            y=plot_skills_df["스킬명"],
                            x=plot_skills_df["장식주 레벨"],
                            orientation="h",
                            name="💎 장식주 추가 스킬",
                            marker=dict(color="#0d9488", cornerradius=4),
                            text=plot_skills_df["레벨 표기"],
                            textposition="outside",
                            cliponaxis=False,
                            customdata=plot_skills_df[["발동 효과", "기여 부위"]],
                            hovertemplate=(
                                "<b>%{y}</b> (장식주 +%{x})<br>"
                                "효과: %{customdata[0]}<br>"
                                "기여: %{customdata[1]}<extra></extra>"
                            ),
                        )
                    )
                if has_overflow:
                    fig_bar.add_trace(
                        go.Bar(
                            y=plot_skills_df["스킬명"],
                            x=plot_skills_df["초과 레벨"],
                            orientation="h",
                            name="초과 레벨",
                            marker=dict(color="#b91c1c", cornerradius=4),
                            hovertemplate="<b>%{y}</b> 초과 레벨: +%{x}<extra></extra>",
                        )
                    )

                fig_bar.update_layout(
                    barmode="stack",
                    template="plotly_white",
                    height=420,
                    paper_bgcolor="#fbf8f1",
                    plot_bgcolor="#f4efe6",
                    font=dict(color="#2b2118", size=12),
                    xaxis=dict(
                        title="스킬 레벨",
                        range=[0, max_x * 1.42],
                        dtick=1,
                        gridcolor="#dfd3c0",
                        linecolor="#cbb89d",
                    ),
                    yaxis=dict(
                        title="",
                        automargin=True,
                        tickfont=dict(size=13, color="#2b2118"),
                    ),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=20, r=50, t=35, b=35),
                )
                st.plotly_chart(fig_bar, width="stretch")

    if not active_skills_df.empty:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">✨ 발동 스킬 상세 효과 및 파츠·장식주 기여도</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                active_skills_df[["스킬명", "분류", "레벨 표기", "발동 효과", "기여 부위"]],
                width="stretch",
                hide_index=True,
                column_config={
                    "스킬명": st.column_config.TextColumn("스킬명", width="medium"),
                    "분류": st.column_config.TextColumn("분류", width="small"),
                    "레벨 표기": st.column_config.TextColumn("달성 레벨", width="medium"),
                    "발동 효과": st.column_config.TextColumn("발동 효과 설명", width="large"),
                    "기여 부위": st.column_config.TextColumn("기여 파츠 및 장식주", width="medium"),
                },
            )


@st.fragment
def render_explorer_tab(armor_df: pd.DataFrame) -> None:
    """탭 2: 방어구 스탯 탐색기 (@st.fragment 부분 렌더링 적용)"""
    with st.container(border=True):
        f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([2.2, 1.1, 1.1, 1.2, 1.4])

        with f_col1:
            skill_search = st.text_input(
                "스킬 / 방어구 / 세트 검색",
                placeholder="예: 약점특효, 도전자, 체술, 고어, 레다우, 알슈...",
            )

        with f_col2:
            part_options = ["전체"] + list(PART_KR_MAP.values())
            selected_part = st.selectbox("장비 부위", options=part_options, index=0)

        with f_col3:
            rank_options = ["전체"] + list(RANK_KR_MAP.values())
            selected_rank = st.selectbox("헌터 랭크", options=rank_options, index=0)

        with f_col4:
            rarity_options = {
                0: "전체 레어도",
                5: "RARE 5 이상",
                6: "RARE 6 이상",
                7: "RARE 7 이상",
                8: "RARE 8 전용",
            }
            min_rarity = st.selectbox(
                "최소 레어도",
                options=list(rarity_options.keys()),
                format_func=lambda k: rarity_options[k],
                index=0,
            )

        with f_col5:
            sort_options = {
                "efficiency_score": "가성비 점수순 (스킬+슬롯)",
                "defense_base": "기본 방어력 높은순",
                "defense_max": "최대 방어력 높은순",
                "slot_score": "슬롯 밸류 높은순",
                "res_total": "속성 내성 합계순",
            }
            sort_by = st.selectbox(
                "정렬 기준",
                options=list(sort_options.keys()),
                format_func=lambda k: sort_options[k],
                index=0,
            )

    mask = pd.Series(True, index=armor_df.index)

    if skill_search.strip():
        kw = skill_search.strip().lower()
        mask &= armor_df["search_blob"].str.contains(kw, regex=False, na=False)

    if selected_part != "전체":
        mask &= armor_df["part_kr"] == selected_part

    if selected_rank != "전체":
        mask &= armor_df["rank_kr"] == selected_rank

    if min_rarity > 0:
        mask &= armor_df["rarity"] >= min_rarity

    filtered_df = armor_df.loc[mask].sort_values(
        by=[sort_by, "defense_base", "rarity"], ascending=[False, False, False]
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("조회된 방어구", f"{len(filtered_df):,} 개")
    m2.metric(
        "최고 가성비 점수 (스킬+슬롯)",
        f"{filtered_df['efficiency_score'].max()} 점" if not filtered_df.empty else "0 점",
    )
    m3.metric(
        "평균 기본 / 최대 방어력",
        f"{filtered_df['defense_base'].mean():.0f} / {filtered_df['defense_max'].mean():.0f}"
        if not filtered_df.empty
        else "0 / 0",
    )
    m4.metric(
        "최상위 추천 파츠",
        f"{filtered_df.iloc[0]['name']}" if not filtered_df.empty else "-",
    )

    if filtered_df.empty:
        st.info("조건에 일치하는 방어구가 없습니다. 검색어나 필터 조건을 변경해 보세요.")
    else:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">📋 방어구 상세 스탯 목록</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="chart-caption">표 상단의 각 컬럼 제목을 클릭하면 오름차순·내림차순으로 정렬할 수 있습니다.</div>',
                unsafe_allow_html=True,
            )
            display_df = filtered_df[
                [
                    "name",
                    "armor_set",
                    "part_kr",
                    "rank_kr",
                    "rarity",
                    "efficiency_score",
                    "defense_base",
                    "defense_max",
                    "slots_str",
                    "skills_summary",
                    "res_fire",
                    "res_water",
                    "res_thunder",
                    "res_ice",
                    "res_dragon",
                ]
            ]

            st.dataframe(
                display_df,
                width="stretch",
                hide_index=True,
                height=620,
                column_config={
                    "name": st.column_config.TextColumn("방어구명", width="medium"),
                    "armor_set": st.column_config.TextColumn("세트명", width="medium"),
                    "part_kr": st.column_config.TextColumn("부위", width="small"),
                    "rank_kr": st.column_config.TextColumn("랭크", width="small"),
                    "rarity": st.column_config.NumberColumn("레어도", format="R%d", width="small"),
                    "efficiency_score": st.column_config.NumberColumn(
                        "가성비 점수",
                        help="보유 스킬 레벨 합 + 장식주 슬롯 레벨 합",
                        format="%d점",
                        width="small",
                    ),
                    "defense_base": st.column_config.NumberColumn("기본 방어", width="small"),
                    "defense_max": st.column_config.NumberColumn("최대 방어", width="small"),
                    "slots_str": st.column_config.TextColumn("장식주 슬롯", width="small"),
                    "skills_summary": st.column_config.TextColumn("보유 스킬", width="large"),
                    "res_fire": st.column_config.NumberColumn("🔥 불", width="small"),
                    "res_water": st.column_config.NumberColumn("💧 물", width="small"),
                    "res_thunder": st.column_config.NumberColumn("⚡ 번개", width="small"),
                    "res_ice": st.column_config.NumberColumn("❄️ 얼음", width="small"),
                    "res_dragon": st.column_config.NumberColumn("🐉 용", width="small"),
                },
            )


@st.fragment
def render_dictionary_tab(
    decorations_df: pd.DataFrame,
    armor_sets_df: pd.DataFrame,
    skills_df: pd.DataFrame,
) -> None:
    """탭 3: 세트 · 스킬 · 장식주 도감 (@st.fragment 부분 렌더링 적용)"""
    dict_sub1, dict_sub2, dict_sub3 = st.tabs(
        ["💎 장식주 도감", "🥋 방어구 세트 도감", "✨ 전체 스킬 도감"]
    )
    with dict_sub1:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">💎 전체 장식주 도감 (방어구용 & 무기용)</div>',
                unsafe_allow_html=True,
            )
            deco_view = decorations_df[
                ["name", "kind_kr", "slot", "rarity", "skills_summary", "description"]
            ].rename(
                columns={
                    "name": "장식주명",
                    "kind_kr": "장착 구분",
                    "slot": "필요 슬롯",
                    "rarity": "레어도",
                    "skills_summary": "발동 스킬",
                    "description": "설명",
                }
            )
            st.dataframe(deco_view, width="stretch", hide_index=True, height=540)

    with dict_sub2:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">🥋 방어구 세트 도감</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                armor_sets_df.drop(columns=["set_id"], errors="ignore"),
                width="stretch",
                hide_index=True,
                height=540,
            )

    with dict_sub3:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">✨ 전체 스킬 도감</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                skills_df,
                width="stretch",
                hide_index=True,
                height=540,
            )


def main() -> None:
    # ------------------------------------------------------------------------
    # 사이드바: 헌터 길드 아카이브 제어판
    # ------------------------------------------------------------------------
    with st.sidebar:
        st.markdown(
            """
            <div class="guild-sidebar-header">
                <div class="en-sub">FORBIDDEN LANDS COMMISSION</div>
                <h3>⚔️ 헌터 길드 공방</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

        armor_df = load_armor_dataframe("ko")
        armor_sets_df = load_armor_sets_dataframe("ko")
        skills_df, skill_lookup = load_skills_dataframe("ko")
        decorations_df = load_decorations_dataframe("ko")
        sim_tables = build_simulator_lookup_tables("ko")

        st.markdown("**📜 길드 서고 등록 현황**")
        st.metric("등록된 방어구 파츠", f"{len(armor_df):,} 개")
        st.metric("방어구 풀세트", f"{len(armor_sets_df):,} 종")
        st.metric("방어구 / 무기 장식주", f"{len(decorations_df):,} 종")
        st.metric("전투/생존 스킬", f"{len(skills_df):,} 종")

        st.divider()
        if st.button("🔄 길드 데이터 동기화 (API 최신화)", width="stretch"):
            with st.spinner("원격 서버에서 최신 패치 데이터를 병렬 동기화하는 중..."):
                sync_remote_snapshot("ko")
                st.cache_data.clear()
            st.rerun()

    # ------------------------------------------------------------------------
    # 상단 히어로 배너
    # ------------------------------------------------------------------------
    st.markdown(
        """
        <div class="wilds-hero-banner">
            <div class="wilds-hero-left">
                <div class="wilds-emblem">
                    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#e5c158" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2L3 7v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z"/>
                        <path d="M12 6v12"/>
                        <path d="M8 10l4-2 4 2"/>
                        <path d="M8 14l4 2 4-2"/>
                    </svg>
                </div>
                <div class="wilds-title-group">
                    <div class="en-label">MONSTER HUNTER WILDS · HUNTER'S SMITHY ARCHIVE</div>
                    <h1>몬스터헌터 와일즈 장비 대시보드</h1>
                    <p>금지된 땅 조사단 5부위 방어구 & 장식주 커스텀 시뮬레이터 · 상세 스탯 도감</p>
                </div>
            </div>
            <div class="wilds-badge-right">
                GUILD RECORD · WILDS DB
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_builder, tab_explorer, tab_dict = st.tabs(
        [
            "⚒️ 커스텀 장비 시뮬레이터",
            "📜 방어구 스탯 탐색기",
            "📖 세트 · 스킬 · 장식주 도감",
        ]
    )

    with tab_builder:
        render_simulator_tab(sim_tables, skill_lookup)

    with tab_explorer:
        render_explorer_tab(armor_df)

    with tab_dict:
        render_dictionary_tab(decorations_df, armor_sets_df, skills_df)


if __name__ == "__main__":
    main()
