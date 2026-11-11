import io
import json
import os
import re
import time
from typing import List
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Inches, Pt, RGBColor
from google import genai
from google.genai import types
import pandas as pd
from pydantic import BaseModel, Field
import streamlit as st

st.set_page_config(
    page_title="AI 기반 수학 수업자료 제작 플랫폼",
    page_icon="📐",
    layout="wide",
)


# ---------------------------------------------------------
# 0. Pydantic 스키마 정의 (완성형 활동지 및 교사용 자료 구조)
# ---------------------------------------------------------
class ActivityArea(BaseModel):
  영역제목: str = Field(
      description=(
          "예: 1. 개념 발견 및 상황 이해, 2. 수학적 표현과 관계 탐색 등"
      )
  )
  탐구질문_및_활동지시문: str = Field(
      description="학생이 수행할 구체적인 탐구 내용 및 질문 (LaTeX 수식 포함)"
  )
  작성공간_설명: str = Field(
      description="학생이 풀이/기록할 공간에 대한 안내"
  )


class StudentActivitySheet(BaseModel):
  활동지제목: str = Field(description="수업 주제에 맞는 매력적인 활동지 제목")
  학습목표: str = Field(description="이 활동을 통해 달성할 학습 목표")
  영역목록: List[ActivityArea] = Field(
      description="2×2 구조에 맞춘 4개의 핵심 탐구 영역"
  )
  마무리적용문제: str = Field(
      description="활동지 하단에 배치할 최종 적용 및 정리 문제"
  )


class ScoringStep(BaseModel):
  단계: str = Field(description="채점 기준 단계 요약")
  배점: str = Field(description="인정 배점")


class SubQuestionSolution(BaseModel):
  문항번호: str = Field(description="예: 영역 1, 영역 2 또는 문항 1, 2")
  모범답안: str = Field(description="상세한 모범 풀이 과정")
  채점기준: List[ScoringStep] = Field(description="단계별 부분 점수 기준")


class TeacherSolutionModel(BaseModel):
  정답_및_해설목록: List[SubQuestionSolution] = Field(
      description="모든 문항/영역별 상세 정답 및 해설"
  )


class TeacherLessonPlan(BaseModel):
  수업목표: str = Field(description="50분 기준 수업 목표")
  준비물: str = Field(description="필요한 교구 및 학습지")
  도입_동기유발: str = Field(description="수업 시작 5분 도입 가이드")
  활동별시간배분: str = Field(description="영역별 상세 시간 배분")
  핵심발문_및_교사지도요령: str = Field(
      description="교사가 던져야 할 핵심 발문과 오개념 지도 방안"
  )
  정리_및_형성평가: str = Field(description="수업 마무리 정리 방법")


class DifferentiatedSheets(BaseModel):
  기초형_조정사항: str = Field(
      description="핵심 개념 이해 중심, 힌트와 기본 수치가 제공되는 형태"
  )
  기본형_조정사항: str = Field(
      description="표준 성취기준에 적합한 본래의 탐구 활동형"
  )
  심화형_조정사항: str = Field(
      description="조건 변형 및 복합적 사고·일반화 확장형"
  )


class CompleteAssessmentPackage(BaseModel):
  학생용활동지: StudentActivitySheet
  교사용해설: TeacherSolutionModel
  교사용지도안: TeacherLessonPlan
  수준별활동지안내: DifferentiatedSheets


# ---------------------------------------------------------
# 1. API 호출 및 안전한 파싱 함수
# ---------------------------------------------------------
def clean_and_parse_json(raw_text: str):
  cleaned = raw_text.strip()
  if cleaned.startswith("```json"):
    cleaned = cleaned[7:]
  elif cleaned.startswith("```"):
    cleaned = cleaned[3:]
  if cleaned.endswith("```"):
    cleaned = cleaned[:-3]
  cleaned = cleaned.strip()

  try:
    return json.loads(cleaned)
  except json.JSONDecodeError:
    fixed = re.sub(r'\\([a-zA-Z])', r'\\\\\1', cleaned)
    return json.loads(fixed)


def generate_complete_package_with_ai(
    api_key: str,
    subject: str,
    unit: str,
    code: str,
    content: str,
    task_type: str,
    source_archetype: str,
):
  client = genai.Client(api_key=api_key)

  prompt = f"""당신은 대한민국 고등학교 수학과 2022 개정 교육과정 수석 교육과정 전문가이자 교과서 집필위원입니다.
아래 성취기준과 조건에 맞춰, 교사가 인쇄하여 학생에게 바로 배부할 수 있는 **완성형 학생용 수학 활동지**와 **교사용 수업 자료(해설, 지도안, 수준별 안내)**를 구조화된 JSON으로 생성하세요.

[출제 정보]
- 과목: {subject}
- 단원: {unit}
- 성취기준: [{code}] {content}
- 평가/활동 유형: {task_type}
- 벤치마킹 출처 스타일: {source_archetype}

[작성 지침]
1. 학생용 활동지는 교사의 추가 설명 없이도 학생 스스로 읽고 탐구할 수 있도록 완결성 있게 작성할 것.
2. 학생용 활동지의 본문 영역은 2×2 구조(총 4개 영역: 개념발견, 수학적표현, 핵심탐구, 적용정리)로 구성할 것.
3. 교사용 해설과 수업 지도안은 학생용 활동지와 완벽하게 연계될 것.
4. 모든 수학 기호와 수식은 표준 LaTeX 형식($...$)으로 작성할 것."""

  max_retries = 3
  backoff_factor = 2

  for attempt in range(max_retries):
    try:
      response = client.models.generate_content(
          model="gemini-2.5-flash",
          contents=prompt,
          config=types.GenerateContentConfig(
              response_mime_type="application/json",
              response_schema=CompleteAssessmentPackage,
              temperature=0.3,
          ),
      )
      return clean_and_parse_json(response.text)
    except Exception as e:
      if "503" in str(e) or "UNAVAILABLE" in str(e):
        if attempt < max_retries - 1:
          time.sleep(backoff_factor**attempt)
          continue
      raise e


# ---------------------------------------------------------
# 2. Word(.docx) 시험지 및 활동지 결재 양식 생성 함수
# ---------------------------------------------------------
def create_complete_package_docx(
    subject, unit, code, content, package_data
):
  doc = Document()

  sections = doc.sections
  for section in sections:
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

  style = doc.styles["Normal"]
  font = style.font
  font.name = "맑은 고딕"
  font.size = Pt(10)
  font.color.rgb = RGBColor(0x33, 0x33, 0x33)

  # [1] 상단 결재란 (교사 업무용)
  approval_table = doc.add_table(rows=2, cols=4)
  approval_table.alignment = WD_TABLE_ALIGNMENT.RIGHT
  approval_col_widths = [Inches(0.8), Inches(0.8), Inches(0.8), Inches(0.8)]

  for i, text in enumerate(["담당", "계장", "교감", "교장"]):
    cell = approval_table.cell(0, i)
    cell.width = approval_col_widths[i]
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    shading = parse_xml(r'<w:shd {} w:fill="E0E0E0"/>'.format(nsdecls("w")))
    cell._tc.get_or_add_tcPr().append(shading)

  for i in range(4):
    approval_table.cell(1, i).width = approval_col_widths[i]

  def set_table_borders(table, color="CCCCCC"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="4" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="single" w:sz="4" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="{color}"/>'
        f'<w:right w:val="single" w:sz="4" w:space="0" w:color="{color}"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{color}"/>'
        f'<w:insideV w:val="single" w:sz="4" w:space="0" w:color="{color}"/>'
        f"</w:tblBorders>"
    )
    tblPr.append(borders)

  set_table_borders(approval_table)
  doc.add_paragraph()

  # [2] 학생용 활동지 본문 생성
  sheet = package_data.get("학생용활동지", {})
  doc.add_heading(
      f"[수학 탐구 활동지] {sheet.get('활동지제목', '수학 탐구 학습')}", level=1
  )

  info_table = doc.add_table(rows=2, cols=4)
  info_data = [
      ("과목", subject, "단원", unit),
      ("소속/학번/이름", "고등학교 [   ]학년 [   ]반 [   ]번", "성명", "___________"),
  ]
  for r_idx, row_info in enumerate(info_data):
    for c_idx, text in enumerate(row_info):
      cell = info_table.cell(r_idx, c_idx)
      p = cell.paragraphs[0]
      run = p.add_run(text)
      if c_idx % 2 == 0:
        run.bold = True
  set_table_borders(info_table)
  doc.add_paragraph()

  doc.add_paragraph(f"📌 학습 목표: {sheet.get('학습목표', '')}")
  doc.add_paragraph(f"📌 관련 성취기준: [{code}] {content}")
  doc.add_paragraph("---")

  for area in sheet.get("영역목록", []):
    doc.add_heading(area.get("영역제목", "탐구 영역"), level=2)
    doc.add_paragraph(area.get("탐구질문_및_활동지시문", ""))
    p_box = doc.add_paragraph(
        f"[풀이 및 기록 공간] 👉 {area.get('작성공간_설명', '')}"
    )
    p_box.paragraph_format.left_indent = Inches(0.2)
    doc.add_paragraph()

  doc.add_heading("📌 마무리 적용 문제", level=2)
  doc.add_paragraph(sheet.get("마무리적용문제", ""))

  doc.add_page_break()

  # [3] 교사용 정답 및 상세 해설
  doc.add_heading("📁 [교사용 자료] 정답 및 상세 해설", level=1)
  sol = package_data.get("교사용해설", {})
  for item in sol.get("정답_및_해설목록", []):
    doc.add_heading(f"▶ {item.get('문항번호', '')} 해설", level=2)
    doc.add_paragraph(f"[모범 답안]\n{item.get('모범답안', '')}")
    doc.add_paragraph("[채점 기준]")
    for step in item.get("채점기준", []):
      doc.add_paragraph(
          f" - {step.get('단계', '')} (배점: {step.get('배점', '')})"
      )
    doc.add_paragraph()

  doc.add_page_break()

  # [4] 교사용 수업 지도안
  doc.add_heading("📁 [교사용 자료] 50분 수업 지도안", level=1)
  plan = package_data.get("교사용지도안", {})
  doc.add_paragraph(f"• 수업 목표: {plan.get('수업목표', '')}")
  doc.add_paragraph(f"• 준비물: {plan.get('준비물', '')}")
  doc.add_paragraph(f"• 도입 및 동기유발: {plan.get('도입_동기유발', '')}")
  doc.add_paragraph(f"• 영역별 시간 배분: {plan.get('활동별시간배분', '')}")
  doc.add_paragraph(
      f"• 핵심 발문 및 지도 방안: {plan.get('핵심발문_및_교사지도요령', '')}"
  )
  doc.add_paragraph(f"• 정리 및 평가: {plan.get('정리_및_형성평가', '')}")

  buffer = io.BytesIO()
  doc.save(buffer)
  buffer.seek(0)
  return buffer


# ---------------------------------------------------------
# 3. 성취기준 데이터 (7개 과목, 130개)
# ---------------------------------------------------------
ALL_STANDARDS_DATA = [
    (
        "공통수학1",
        "다항식",
        "10공수1-01-01",
        "다항식의 사칙연산의 원리를 설명하고, 그 계산을 할 수 있다.",
    ),
    (
        "공통수학1",
        "다항식",
        "10공수1-01-02",
        "항등식의 성질과 나머지정리를 이해하고, 이를 활용하여 문제를 해결할 수 있다.",
    ),
    (
        "미적분Ⅰ",
        "미분",
        "12미적1-02-04",
        "함수의 증가와 감소, 극대와 극소를 판정하고 함수의 그래프의 개형을 그릴 수"
        " 있다.",
    ),
    (
        "미적분Ⅰ",
        "미분",
        "12미적1-02-05",
        "도함수를 방정식, 부등식, 속도와 가속도에 활용할 수 있다.",
    ),
    (
        "확률과 통계",
        "통계",
        "12확통03-04",
        "표본평균의 분포를 이해하고, 모평균의 신뢰구간을 구할 수 있다.",
    ),
]
df_standards = pd.DataFrame(
    ALL_STANDARDS_DATA, columns=["과목", "단원", "성취기준코드", "성취기준내용"]
)


# ---------------------------------------------------------
# 4. 사이드바 설정
# ---------------------------------------------------------
with st.sidebar:
  st.header("⚙️ 플랫폼 환경 설정")
  default_key = os.environ.get("GEMINI_API_KEY", "")
  try:
    if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
      default_key = st.secrets["GEMINI_API_KEY"]
  except Exception:
    pass

  api_key_input = st.text_input(
      "Gemini API Key",
      value=default_key,
      type="password",
      help="Google AI Studio에서 발급받은 API 키를 입력하세요.",
  )

  if api_key_input:
    st.success("API 키 로드 완료", icon="🔑")
  else:
    st.error("활동지 생성을 위해 Gemini API 키가 필수입니다.")


# ---------------------------------------------------------
# 5. 메인 레이아웃
# ---------------------------------------------------------
st.title("📐 AI 기반 수학 수업자료 제작 플랫폼")
st.caption(
    "교사가 과목과 성취기준을 선택하면 학생용 활동지, 교사용 지도안, 상세"
    " 해설을 자동으로 완성합니다."
)
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
  st.subheader("1. 성취기준 선택")
  subject_list = df_standards["과목"].unique().tolist()
  selected_subject = st.selectbox("과목 선택", subject_list)

  filtered_by_subj = df_standards[df_standards["과목"] == selected_subject]
  unit_list = filtered_by_subj["단원"].unique().tolist()
  selected_unit = st.selectbox("단원 선택", unit_list)

  filtered_by_unit = filtered_by_subj[filtered_by_subj["단원"] == selected_unit]
  code_list = filtered_by_unit["성취기준코드"].tolist()
  code_to_content = dict(
      zip(filtered_by_unit["성취기준코드"], filtered_by_unit["성취기준내용"])
  )

  selected_code = st.selectbox(
      "성취기준 선택",
      code_list,
      format_func=lambda c: f"[{c}] {code_to_content[c]}",
  )
  selected_content = code_to_content[selected_code]

with col2:
  st.subheader("2. 수업 및 출처 스타일 설정")
  task_type = st.selectbox(
      "탐구 및 평가 활동 유형",
      [
          "개념 탐구 및 실생활 문제해결 활동지",
          "수학적 모델링 및 추론 탐구",
          "서·논술형 지필평가 연계 활동",
          "모둠별 과제 탐구 활동",
      ],
  )
  source_archetype = st.selectbox(
      "자료 벤치마킹 스타일",
      [
          "시도교육청 우수 서·논술형 활동지 스타일",
          "수학교과서 심화 탐구 활동 스타일",
          "교육과정 평가원 우수 수업 자료 스타일",
      ],
  )
  st.info(
      f"**선택된 성취기준:** [{selected_code}]\n\n**스타일:**"
      f" {source_archetype}"
  )

st.markdown("---")

if st.button(
    "🚀 완성형 수학 활동지 및 교사용 자료 자동 생성",
    type="primary",
    use_container_width=True,
):
  if not api_key_input:
    st.error("사이드바에 Gemini API 키를 입력해 주세요.")
  else:
    with st.spinner(
        f"[{selected_code}] 성취기준 기반 학생용 활동지와 교사용 자료 패키지를"
        " 생성 중입니다..."
    ):
      try:
        package_result = generate_complete_package_with_ai(
            api_key_input,
            selected_subject,
            selected_unit,
            selected_code,
            selected_content,
            task_type,
            source_archetype,
        )
        st.session_state["complete_package"] = package_result
        st.session_state["sel_subj"] = selected_subject
        st.session_state["sel_unit"] = selected_unit
        st.session_state["sel_code"] = selected_code
        st.session_state["sel_content"] = selected_content
        st.success("수업 자료 패키지 생성 완료!")
      except Exception as e:
        st.error(f"생성 중 오류가 발생했습니다: {str(e)}")
        st.session_state["complete_package"] = None


# ---------------------------------------------------------
# 6. 결과 출력 영역 (4대 핵심 탭)
# ---------------------------------------------------------
if "complete_package" in st.session_state and st.session_state[
    "complete_package"
]:
  pkg = st.session_state["complete_package"]
  subj = st.session_state.get("sel_subj", "")
  unit = st.session_state.get("sel_unit", "")
  code = st.session_state.get("sel_code", "")
  content = st.session_state.get("sel_content", "")

  docx_buffer = create_complete_package_docx(subj, unit, code, content, pkg)
  st.download_button(
      label="📥 전체 수업 자료 패키지 Word(.docx) 다운로드 (활동지+해설+지도안)",
      data=docx_buffer,
      file_name=f"수학수업자료_{code}.docx",
      mime=(
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      ),
      use_container_width=True,
      type="primary",
  )
  st.markdown("---")

  tab1, tab2, tab3, tab4 = st.tabs([
      "📄 1. 학생용 활동지 미리보기",
      "👩‍🏫 2. 교사용 수업 지도안",
      "🎯 3. 정답 및 상세 해설",
      "📊 4. 수준별 활동지 안내",
  ])

  # [탭 1] 학생용 활동지
  with tab1:
    sheet = pkg.get("학생용활동지", {})
    st.markdown(f"## 📄 {sheet.get('활동지제목', '수학 탐구 활동지')}")
    st.info(f"**학습 목표:** {sheet.get('학습목표', '')}")

    st.markdown("---")
    st.markdown("### 🧩 탐구 본문 (2×2 영역 구성)")

    areas = sheet.get("영역목록", [])
    for i in range(0, len(areas), 2):
      col_a, col_b = st.columns(2)
      with col_a:
        if i < len(areas):
          a1 = areas[i]
          st.container(border=True)
          st.markdown(f"#### {a1.get('영역제목', '')}")
          st.markdown(a1.get("탐구질문_및_활동지시문", ""))
          st.caption(
              f"✍️ [기록 공간] {a1.get('작성공간_설명', '풀이를 작성하세요.')}"
          )
      with col_b:
        if i + 1 < len(areas):
          a2 = areas[i + 1]
          st.container(border=True)
          st.markdown(f"#### {a2.get('영역제목', '')}")
          st.markdown(a2.get("탐구질문_및_활동지시문", ""))
          st.caption(
              f"✍️ [기록 공간] {a2.get('작성공간_설명', '풀이를 작성하세요.')}"
          )

    st.markdown("---")
    st.markdown("### 📌 마무리 적용 문제")
    st.write(sheet.get("마무리적용문제", ""))

  # [탭 2] 교사용 수업 지도안
  with tab2:
    st.subheader("👩‍🏫 50분 수업 지도안")
    plan = pkg.get("교사용지도안", {})
    st.write(f"**• 수업 목표:** {plan.get('수업목표', '')}")
    st.write(f"**• 준비물:** {plan.get('준비물', '')}")
    st.write(f"**• 도입 및 동기유발:** {plan.get('도입_동기유발', '')}")
    st.write(f"**• 영역별 시간 배분:** {plan.get('활동별시간배분', '')}")
    st.write(
        f"**• 핵심 발문 및 지도 방안:**"
        f" {plan.get('핵심발문_및_교사지도요령', '')}"
    )
    st.write(f"**• 정리 및 평가:** {plan.get('정리_및_형성평가', '')}")

  # [탭 3] 정답 및 상세 해설
  with tab3:
    st.subheader("🎯 정답 및 상세 해설")
    sol = pkg.get("교사용해설", {})
    for item in sol.get("정답_및_해설목록", []):
      st.markdown(f"#### **{item.get('문항번호', '')} 해설**")
      with st.expander("모범 답안 보기", expanded=True):
        st.markdown(item.get("모범답안", ""))
      st.markdown("**[채점 기준]**")
      for step in item.get("채점기준", []):
        st.markdown(
            f"- {step.get('단계', '')} *(배점: {step.get('배점', '')})*"
        )
      st.markdown("---")

  # [탭 4] 수준별 활동지 안내
  with tab4:
    st.subheader("📊 수준별(기초·기본·심화) 활동지 조정 가이드")
    diff = pkg.get("수준별활동지안내", {})
    col_l, col_m, col_r = st.columns(3)
    with col_l:
      st.info("🟢 **기초형 (하)**")
      st.write(diff.get("기초형_조정사항", ""))
    with col_m:
      st.success("🔵 **기본형 (중)**")
      st.write(diff.get("기본형_조정사항", ""))
    with col_r:
      st.warning("🟣 **심화형 (상)**")
      st.write(diff.get("심화형_조정사항", ""))
