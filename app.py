from __future__ import annotations

import json
import os
import time
from pathlib import Path

import streamlit as st
from engine import create_store, generate_package

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"

st.set_page_config(
    page_title="수학 탐구·평가 스튜디오",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { --navy:#17243a; --blue:#315efb; --line:#e5eaf3; }
    .stApp { background:#f7f9fd; }
    [data-testid="stHeader"] { background:rgba(247,249,253,.92); }
    .block-container { padding-top:1.3rem; padding-bottom:3rem; max-width:1440px; }
    [data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--line); }
    .hero { border-radius:22px; padding:28px 32px; color:white;
      background:linear-gradient(120deg,#17243a 0%,#253d68 55%,#315efb 100%);
      box-shadow:0 12px 32px rgba(26,46,83,.14); margin-bottom:18px; }
    .hero-kicker { font-size:11px; letter-spacing:.16em; font-weight:800; opacity:.75; }
    .hero h1 { color:white; font-size:clamp(25px,3vw,36px); font-weight:800; margin:8px 0 5px; }
    .hero p { color:#e1e9ff; font-size:14px; margin:0; }
    .metric { background:white; border:1px solid var(--line); border-radius:16px;
      padding:15px 17px; min-height:94px; box-shadow:0 3px 12px rgba(32,52,88,.035); }
    .metric-label { color:#72809a; font-size:12px; margin-bottom:5px; }
    .metric-value { color:var(--navy); font-size:24px; line-height:1.2; font-weight:800; }
    .metric-note { color:#8793a8; font-size:11px; margin-top:4px; }
    .section-title { color:var(--navy); font-weight:800; font-size:18px; margin:8px 0 4px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; border-color:var(--line); }
    .stButton button[kind="primary"] { border-radius:12px; min-height:48px;
      font-weight:800; background:var(--blue); border-color:var(--blue); }
    .stDownloadButton button { border-radius:10px; font-weight:650; }
    [data-testid="stTabs"] button { font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, None)
    except Exception:
        value = None
    return str(value or os.getenv(name, default) or default)


@st.cache_resource
def load_store():
    required = [
        "achievement_standards.json", "all_concepts.json",
        "all_misconceptions.json", "all_inquiry_activities.json",
        "all_item_blueprints.json", "all_standard_concept_map.json",
        "all_scope_guardrails.json", "area_guidance.json",
        "design_principles.json", "concept_relations.json",
        "assessment_package.schema.json", "gemini_generation.schema.json",
    ]
    missing = [name for name in required if not (DATA_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "필수 지식 데이터 파일이 없습니다: " + ", ".join(missing)
            + f" | 확인 경로: {DATA_DIR}"
        )
    return create_store(DATA_DIR)


st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">AI MATH DESIGN WORKSPACE · 2022 REVISED CURRICULUM</div>
      <h1>수학 탐구·평가 스튜디오</h1>
      <p>성취기준에서 출발해 탐구 수업, 완결형 문항, A~E 평가기준까지 한 번에 설계합니다.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    store = load_store()
except Exception as exc:
    st.error("지식 데이터 로딩에 실패했습니다.")
    st.code(str(exc))
    st.info("GitHub 저장소 최상위에 app.py와 같은 위치로 data/ 폴더를 업로드했는지 확인하세요.")
    st.stop()

courses = store.list_courses()
total_standards = sum(len(store.list_standards(c["course_id"])) for c in courses)
m1, m2, m3, m4 = st.columns(4)
for col, label, value, note in [
    (m1, "운영 과목", f"{len(courses)}개", "2022 개정 교육과정"),
    (m2, "공식 성취기준", f"{total_standards}개", "과목별 연결 데이터"),
    (m3, "학습 개념", f"{len(store.concepts)}개", "개념·성취기준 매핑"),
    (m4, "탐구 활동", f"{len(store.activities)}개", "문항 설계와 연계"),
]:
    col.markdown(
        f'<div class="metric"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>',
        unsafe_allow_html=True,
    )

with st.sidebar:
    st.markdown("### ⚙️ 설계 조건")
    st.caption("1. 과목과 성취기준을 선택하세요.")
    course_labels = {
        f"{x['course_name']} · {x['course_category']}": x["course_id"] for x in courses
    }
    course_label = st.selectbox("과목", list(course_labels), key="course_label")
    course_id = course_labels[course_label]
    standards = store.list_standards(course_id)
    units = store.list_units(course_id)
    unit_labels = {u["unit_name"]: u["unit_id"] for u in units}
    unit_name = st.selectbox("단원", list(unit_labels), key="unit_name")
    target_standards = [x for x in standards if x["unit_id"] == unit_labels[unit_name]]
    code_to_record = {x["code"]: x for x in target_standards}
    selected_code = st.selectbox(
        "성취기준", list(code_to_record),
        format_func=lambda code: f"{code} | {code_to_record[code]['content'][:52]}",
        key="standard_code",
    )
    st.divider()
    st.caption("2. 생성 방식을 선택하세요.")
    mode = st.radio("생성 모드", ["Gemini AI 완성형", "오프라인 설계 초안"], index=0)
    api_key = ""
    model = _secret_or_env("GEMINI_MODEL", "gemini-3.5-flash-lite")
    thinking_level = "minimal"
    if mode.startswith("Gemini"):
        saved_key = _secret_or_env("GEMINI_API_KEY")
        if saved_key:
            st.success("Gemini API 키 연결 확인")
        api_key = st.text_input(
            "Gemini API Key", type="password",
            placeholder="Secrets 등록 시 비워두세요",
            help="키는 저장소에 기록하지 않습니다.",
        )
        model_options = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
        model_default = model if model in model_options else model_options[0]
        model = st.selectbox(
            "생성 모델", model_options, index=model_options.index(model_default),
            format_func=lambda x: "Flash-Lite · 빠른 생성" if x == "gemini-3.5-flash-lite" else "Flash · 균형 품질",
        )
        if model == "gemini-3.5-flash-lite":
            speed = st.radio(
                "추론 수준", ["최소 · 가장 빠름", "낮음 · 빠름", "중간 · 정밀"],
                index=0,
            )
            thinking_level = {
                "최소 · 가장 빠름": "minimal",
                "낮음 · 빠름": "low",
                "중간 · 정밀": "medium",
            }[speed]
        else:
            speed = st.radio("추론 수준", ["낮음 · 빠름", "중간 · 정밀"], index=0)
            thinking_level = "low" if speed.startswith("낮음") else "medium"
        st.caption("빠른 모드는 생성 지연을 줄입니다. 결과물은 교사가 검토한 뒤 사용하세요.")
    user_requirements = st.text_area(
        "수업 맞춤 요청 (선택)",
        placeholder="예: 그래프 해석 중심, 실생활 맥락, 50분 수업, 서술형 문항",
        height=92,
    )
    generate_clicked = st.button(
        "✦ 탐구 수업·평가 패키지 생성", type="primary", use_container_width=True
    )
    st.caption("Gemini 요청은 기본 1회입니다. 응답이 도착하면 실시간으로 표시합니다.")

selected = code_to_record[selected_code]
c1, c2 = st.columns([1.7, 1], gap="large")
with c1:
    with st.container(border=True):
        st.markdown('<div class="section-title">선택한 학습 기준</div>', unsafe_allow_html=True)
        st.markdown(f"**{selected['course_name']} · {selected['unit_name']}**")
        st.markdown(f"`{selected['code']}`")
        st.write(selected["content"])
with c2:
    with st.container(border=True):
        st.markdown('<div class="section-title">생성 패키지</div>', unsafe_allow_html=True)
        st.write("① 탐구 수업 설계")
        st.write("② 완결형 평가 문항")
        st.write("③ 모범답안 및 풀이")
        st.write("④ A~E 수준별 채점기준")

if generate_clicked:
    started = time.perf_counter()
    is_gemini = mode.startswith("Gemini")
    effective_key = api_key or _secret_or_env("GEMINI_API_KEY")
    if is_gemini and not effective_key:
        st.error("Gemini API 키가 없습니다. Streamlit Secrets의 GEMINI_API_KEY를 확인하세요.")
    else:
        status_area = st.status("생성 준비 중 · 교육과정 데이터를 확인합니다.", expanded=True)
        stream_area = st.empty()
        stream_code = st.empty()
        latest = {"updated": 0.0}

        def on_chunk(text: str):
            now = time.perf_counter()
            if now - latest["updated"] >= 0.3:
                latest["updated"] = now
                elapsed = now - started
                status_area.update(
                    label=f"Gemini 응답 수신 중 · {len(text):,}자 · {elapsed:.1f}초",
                    state="running", expanded=True,
                )
                stream_area.caption("구조화된 JSON 응답을 실시간 수신하고 있습니다.")
                stream_code.code(text[-900:], language="json")

        try:
            if is_gemini:
                status_area.write(f"모델: {model} · 추론 수준: {thinking_level}")
                status_area.write("완성형 패키지를 한 번의 Gemini 요청으로 생성합니다.")
                status_area.write("첫 응답이 도착하면 실시간 미리보기가 표시됩니다.")
                package = generate_package(
                    store, course_id, selected_code, mode="gemini",
                    api_key=effective_key, model=model,
                    user_requirements=user_requirements or None,
                    thinking_level=thinking_level, on_chunk=on_chunk,
                )
            else:
                package = generate_package(
                    store, course_id, selected_code, mode="offline",
                    user_requirements=user_requirements or None,
                )
            elapsed = time.perf_counter() - started
            package.setdefault("metadata", {})["generation_seconds"] = round(elapsed, 2)
            package["metadata"]["thinking_level"] = thinking_level if is_gemini else "offline"
            package["metadata"]["model"] = model if is_gemini else None
            st.session_state["math_package"] = package
            status_area.update(label=f"생성 완료 · {elapsed:.1f}초", state="complete", expanded=False)
            stream_area.empty()
            stream_code.empty()
            st.success(f"패키지 생성 및 구조 검증 완료 · {elapsed:.1f}초")
        except Exception as exc:
            elapsed = time.perf_counter() - started
            status_area.update(label=f"생성 실패 · {elapsed:.1f}초", state="error", expanded=True)
            st.error(f"{type(exc).__name__}: {exc}")
            st.warning(
                "시간이 길면 Flash-Lite 모델과 최소 추론을 선택하세요. "
                "인증·할당량·모델 오류는 동일 요청을 자동 반복하지 않습니다."
            )

package = st.session_state.get("math_package")
if package:
    st.divider()
    selection = package["selection"]
    st.markdown(
        f'<div class="section-title">생성 결과 · {selection["course_name"]} / {selection["unit_name"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"**{selection['standard_code']}** · {selection['standard_content']}")
    metadata = package.get("metadata", {})
    if metadata.get("generation_seconds") is not None:
        st.caption(
            f"생성 시간 {metadata['generation_seconds']}초 · "
            f"모델 {metadata.get('model') or '오프라인'} · "
            f"추론 {metadata.get('thinking_level', '-')}"
        )
    t1, t2, t3, t4 = st.tabs(["수업 설계", "문항·정답", "A~E 채점기준", "품질 검증"])
    with t1:
        design = package["design"]
        with st.container(border=True):
            st.markdown("#### 핵심 탐구 질문")
            st.markdown(f"### {design['driving_question']}")
            st.write(design["context"])
        a, b = st.columns(2)
        with a:
            st.markdown("#### 학습 목표")
            for obj in design.get("learning_objectives", []):
                st.write("✓ " + obj)
        with b:
            st.markdown("#### 수학적 표현")
            st.write(" · ".join(design.get("representations", [])))
        st.markdown("#### 탐구 흐름")
        for i, step in enumerate(design["inquiry_steps"], 1):
            with st.expander(f"{i:02d} · {step['phase']}", expanded=(i == 1)):
                st.markdown("**교사 활동**")
                st.write(step["teacher_action"])
                st.markdown("**학생이 남길 증거**")
                st.write(step["student_evidence"])
        a, b = st.columns(2)
        with a:
            st.markdown("#### 개별 지원")
            for item in design.get("differentiation", {}).get("support", []):
                st.write("• " + item)
        with b:
            st.markdown("#### 심화·확장")
            for item in design.get("differentiation", {}).get("extension", []):
                st.write("• " + item)
    with t2:
        item = package["item"]
        with st.container(border=True):
            st.caption(f"{item['item_type']} · 인지 수준: {item['cognitive_demand']}")
            st.markdown("#### 평가 문항")
            st.markdown(item["prompt"])
        st.markdown("#### 모범답안")
        st.success(item["expected_answer"])
        st.markdown("#### 단계별 풀이")
        for i, step in enumerate(item.get("solution_steps", []), 1):
            st.write(f"{i}. {step}")
        with st.expander("형성평가 체크"):
            for question in package.get("formative_check", {}).get("questions", []):
                st.write("□ " + question)
    with t3:
        rubric = package["item"]["rubric"]
        st.metric("총점", f"{rubric['total_points']}점")
        for criterion in rubric["criteria"]:
            with st.expander(f"{criterion['criterion']} · {criterion['points']}점"):
                st.table([
                    {"수준": level, "관찰 가능한 수행": desc}
                    for level, desc in criterion["levels"].items()
                ])
    with t4:
        validation = package.get("validation", {})
        st.metric("검증 상태", validation.get("status", "UNKNOWN"))
        for check in validation.get("checks", []):
            mark = "✅" if check.get("status") == "PASS" else "⚠️"
            st.write(f"{mark} **{check.get('name')}** — {check.get('detail')}")
        for warning in validation.get("warnings", []):
            st.warning(warning)

    payload = json.dumps(package, ensure_ascii=False, indent=2)
    st.download_button(
        "⬇ JSON 패키지 다운로드", payload,
        file_name="math_inquiry_assessment.json",
        mime="application/json", use_container_width=True,
    )
else:
    st.info("왼쪽에서 과목과 성취기준을 선택한 뒤 생성 버튼을 눌러 주세요.")
