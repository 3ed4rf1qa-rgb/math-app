# 6단계 — 탐구 기반 수학 문항 자동 생성 엔진

## 목표
1~5단계에서 구축한 2022 개정 고등학교 수학 7개 과목의 성취기준·개념·오개념·탐구 활동·문항 설계 데이터와 출판사 벤치마킹에서 추출한 교수설계 원칙을 연결해 수업 및 평가 패키지를 생성한다.

## 처리 흐름
1. 교사가 과목·단원·공식 성취기준을 선택한다.
2. 성취기준에 연결된 개념, 오개념, 탐구 활동, 문항 템플릿, 과목별 범위 제약을 조회한다.
3. 5단계의 교수설계 원칙을 입력으로 결합한다.
4. 오프라인 설계 초안 또는 Gemini 구조화 JSON 생성으로 수업 흐름·문항·정답·풀이·A~E 루브릭을 만든다.
5. JSON Schema, 성취기준 바인딩, 데이터 참조, 루브릭 점수, A~E 수준을 검사한다.
6. 교사가 결과를 편집하고 승인한 뒤 실제 평가에 사용한다.

## 실행
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

# API 없이 데이터 조회와 스캐폴드 생성 테스트
python cli.py --course HS-CALCULUS-1 --standard-code "12미적Ⅰ-02-05" --mode offline

# Gemini 구조화 생성 (PowerShell)
$env:GEMINI_API_KEY="YOUR_KEY"
python cli.py --course HS-CALCULUS-1 --standard-code "12미적Ⅰ-02-05" --mode gemini --output sample.json

# Streamlit UI
streamlit run app.py

# 자동 테스트
python -m unittest discover -s tests -v
```

기본 모델은 `GEMINI_MODEL` 환경변수를 사용하며 기본값은 `gemini-3.8-flash`이다. API 키는 환경변수 또는 Streamlit 비밀번호 입력란으로만 전달하고 GitHub에 저장하지 않는다.

## 생성 모드
- `offline`: 데이터 연결과 출력 구조를 검증하는 스캐폴드. 완결 문항·정답을 자동 확정하지 않으며 상태가 `SCAFFOLD_ONLY`로 표시된다.
- `gemini`: Gemini JSON Schema 기반 구조화 출력. 모범답안과 풀이가 생성되지만 수학적 정답이 증명되는 것은 아니므로 교사 검토가 필요하다.

## 핵심 파일
- `engine.py`: 지식 조회, 프롬프트 조립, Gemini 연결, 패키지 검증
- `app.py`: Streamlit UI
- `cli.py`: 명령행 인터페이스
- `data/achievement_standards.json`: 공식 성취기준 130개
- `data/all_concepts.json`: 7과목 개념 데이터 130개
- `data/all_misconceptions.json`: 오개념 데이터
- `data/all_inquiry_activities.json`: 탐구 활동
- `data/all_item_blueprints.json`: 문항 설계 템플릿
- `data/all_scope_guardrails.json`: 과목별 출제 범위 제한
- `data/design_principles.json`: 5단계의 12개 교수설계 원칙
- `data/assessment_package.schema.json`: 최종 생성물 스키마
- `tests/test_engine.py`: 전체 과목 조회 및 Gemini 어댑터 모의 통합 테스트

## 검증 범위와 한계
- 자동 테스트는 7개 과목 전체의 성취기준 조회, 데이터 결합, 잘못된 코드/과목 조합 거부, JSON Schema 입력, Gemini 어댑터의 모의 응답 흐름을 확인한다.
- 실제 Gemini API 네트워크 호출은 유효한 사용자 API 키가 없으므로 테스트하지 않았다.
- AI 생성 문항의 수학적 정답, 풀이의 완전성, 평가 신뢰도, 학생 반응은 교사/수학교육 전문가 검토가 필요하다.
- 지식 데이터 내 개념·오개념·탐구 활동은 프로젝트의 자체 작성 교수설계 초안이며, 교사 검토 상태는 `pending`이다.
- 저작권이 있는 출판사 교과서의 문장·문항·이미지·UI를 복사하지 않는다.
