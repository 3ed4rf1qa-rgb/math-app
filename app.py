import json
import os
import streamlit as st
from engine import create_store, generate_package

st.set_page_config(page_title="탐구 기반 수학 문항 생성기", layout="wide")
st.title("탐구 기반 수학 문항 자동 설계")
st.caption("2022 개정 교육과정 공식 성취기준 + 7과목 개념 데이터 + 교수설계 원칙")

@st.cache_resource
def load_store():
    return create_store("data")

store = load_store()
courses = store.list_courses()
course_labels = {f"{x['course_name']} ({x['course_category']})": x["course_id"] for x in courses}

with st.sidebar:
    st.header("생성 조건")
    course_label = st.selectbox("과목", list(course_labels))
    course_id = course_labels[course_label]
    standards = store.list_standards(course_id)
    unit_names = list(dict.fromkeys(x["unit_name"] for x in standards))
    unit_name = st.selectbox("단원", unit_names)
    target_standards = [x for x in standards if x["unit_name"] == unit_name]
    selected_code = st.selectbox(
        "성취기준",
        [x["code"] for x in target_standards],
        format_func=lambda c: f"[{c}] " + next(x["content"] for x in target_standards if x["code"] == c)
    )
    mode = st.radio("생성 방식", ["오프라인 설계 초안", "Gemini AI 완성형 생성"])
    api_key = ""
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    if mode.startswith("Gemini"):
        api_key = st.text_input("Gemini API Key", type="password")
        model = st.text_input("모델명", value=model)
    teacher_requirements = st.text_area("추가 요구사항(선택)", placeholder="예: 실생활 맥락, 그래프 해석 중심, 20분 활동 등")
    run = st.button("탐구 수업 및 평가 패키지 생성", type="primary", use_container_width=True)

st.info("오프라인 초안은 데이터 연결·구조 점검용이며 완결 문항과 정답을 제공하지 않습니다. Gemini 모드 또는 교사 편집 후 사용하세요.")
if run:
    try:
        package = generate_package(
            store, course_id, selected_code,
            mode="gemini" if mode.startswith("Gemini") else "offline",
            api_key=api_key or None, model=model, user_requirements=teacher_requirements or None
        )
        st.session_state["package"] = package
        st.success(f"생성 완료: {package['validation']['status']}")
    except Exception as exc:
        st.error(f"생성 실패: {exc}")

package = st.session_state.get("package")
if package:
    selection = package["selection"]
    st.subheader(f"{selection['course_name']} · {selection['unit_name']}")
    st.write(f"**[{selection['standard_code']}]** {selection['standard_content']}")
    tab1, tab2, tab3, tab4 = st.tabs(["수업 설계", "문항·정답", "A~E 채점기준", "검증"])
    with tab1:
        st.markdown("### " + package["design"]["driving_question"])
        st.write(package["design"]["context"])
        for i, step in enumerate(package["design"]["inquiry_steps"], 1):
            with st.expander(f"{i}. {step['phase']}"):
                st.write("교사 활동:", step["teacher_action"])
                st.write("학생 증거:", step["student_evidence"])
        st.write("개념 표현:", ", ".join(package["design"]["representations"]))
        st.write("지원:", package["design"]["differentiation"]["support"])
        st.write("확장:", package["design"]["differentiation"]["extension"])
    with tab2:
        st.write("**문항 유형:**", package["item"]["item_type"])
        st.markdown(package["item"]["prompt"])
        st.write("**모범답안:**", package["item"]["expected_answer"])
        st.write("**풀이:**")
        for step in package["item"]["solution_steps"]:
            st.write("- " + step)
    with tab3:
        st.write(f"총점: {package['item']['rubric']['total_points']}점")
        for criterion in package["item"]["rubric"]["criteria"]:
            with st.expander(f"{criterion['criterion']} ({criterion['points']}점)"):
                st.table([{"수준": level, "수행기술": descriptor} for level, descriptor in criterion["levels"].items()])
    with tab4:
        st.json(package["validation"])
    payload = json.dumps(package, ensure_ascii=False, indent=2)
    st.download_button("JSON 패키지 다운로드", payload, file_name="math_inquiry_assessment.json", mime="application/json")
