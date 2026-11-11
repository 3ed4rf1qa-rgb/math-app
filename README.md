[README.md](https://github.com/user-attachments/files/34675585/README.md)
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


## Streamlit Community Cloud 배포 (중요)

GitHub 저장소에 ZIP 파일만 올리면 앱은 그 안의 파일을 자동으로 압축 해제하지 않습니다. ZIP을 PC에서 먼저 압축 해제한 뒤, **압축 내부의 프로젝트 파일을 저장소 최상위에 업로드**하세요.

저장소 최상위는 아래 구조여야 합니다.

```text
repository-root/
├── app.py
├── engine.py
├── cli.py
├── requirements.txt
├── README.md
├── data/
│   ├── achievement_standards.json
│   ├── all_concepts.json
│   ├── all_misconceptions.json
│   ├── all_inquiry_activities.json
│   ├── all_item_blueprints.json
│   ├── all_standard_concept_map.json
│   ├── all_scope_guardrails.json
│   ├── area_guidance.json
│   ├── design_principles.json
│   ├── concept_relations.json
│   ├── assessment_package.schema.json
│   └── gemini_generation.schema.json
└── tests/
```

### 배포 순서
1. 이 ZIP을 내려받아 PC에서 압축 해제합니다.
2. 압축을 푼 폴더 안의 모든 파일과 `data/`, `tests/` 폴더를 GitHub 저장소 최상위에 업로드합니다. `data` 폴더를 생략하거나 ZIP만 올리면 안 됩니다.
3. GitHub 저장소 최상위에 `requirements.txt` 파일이 있는지 확인합니다.
4. Streamlit Community Cloud에서 해당 저장소와 브랜치를 선택하고 Main file path를 `app.py`로 지정합니다.
5. 배포 후 먼저 `오프라인 설계 초안`으로 데이터 로딩과 기본 화면을 확인합니다.
6. Gemini 사용 시 API 키를 화면에 입력하거나 Streamlit 앱의 Secrets에 아래처럼 저장합니다.

```toml
GEMINI_API_KEY = "실제_API_키"
GEMINI_MODEL = "gemini-3.8-flash"
```

API 키를 GitHub 코드나 공개 파일에 직접 입력하지 마세요. 앱은 `app.py` 기준의 절대 경로로 `data/`를 읽으므로 실행 작업 디렉터리가 달라져도 데이터 경로가 흔들리지 않습니다. 필수 파일이 빠진 경우에는 빠진 파일명과 확인 경로를 화면에 표시합니다.

### 배포 전 로컬 검증

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python validate_stage6.py
streamlit run app.py
```

현재 검증은 데이터 무결성, 오프라인 생성 흐름, Gemini 모의 응답을 포함합니다. 실제 Gemini API 호출은 유효한 API 키가 설정된 배포 환경에서 별도로 확인해야 합니다.


## Gemini 생성 속도 개선 (배포 설정)

- 기본은 Gemini 3.8 Flash의 `thinking_level=low`로 실행합니다. 긴 추론이 불필요한 수업·평가 초안 생성의 대기 시간을 줄이기 위한 설정입니다.
- 필요할 때만 앱에서 `정밀 생성 (MEDIUM)`을 선택할 수 있습니다.
- 한 번의 완성형 요청은 Gemini API를 1회 호출합니다. 인증/모델/스키마 오류를 같은 내용으로 무조건 재요청하지 않습니다.
- 네트워크 요청 타임아웃은 120초이며 SDK 내부 자동 재시도를 비활성화해 예상하지 못한 중복 대기를 방지합니다.
- 사용 모델 기본값은 `gemini-3.8-flash`; 더 빠른 모델 선택지로 `gemini-3.5-flash-lite`를 제공합니다. 모델별 이용 가능 여부는 Google AI Studio 프로젝트/지역/계정 설정에 따라 달라질 수 있습니다.
- 생성 결과는 자동 구조 검사 후 교사 검토가 필요합니다. 빠른 생성은 모델의 추론 수준을 낮추는 것이므로 수학적 정답 검토를 생략하지 않습니다.


## 빠른 생성과 실시간 응답 표시 (개선판)

이 배포판은 Gemini 응답을 받을 때 스트리밍을 우선 사용합니다. 생성 중에는 수신된 JSON 조각과 경과 시간을 화면에 표시하고, 응답이 완성되면 JSON 파싱·스키마·성취기준 연결·루브릭 검사를 실행합니다.

### 모델 프리셋
- `gemini-3.5-flash-lite` + `minimal`: 가장 빠른 생성 기본값
- `gemini-3.5-flash-lite` + `low/medium`: 빠른 모델에서 더 많은 추론
- `gemini-3.8-flash` + `low/medium`: 품질 균형 및 정밀 생성

Gemini 3.8 Flash는 기본 추론 수준이 medium이며, low로 낮추면 지연 시간과 토큰 사용량을 줄일 수 있습니다. Flash-Lite의 minimal은 속도 중심 설정입니다. 빠른 프리셋은 응답 품질과 수학적 정교함이 달라질 수 있으므로, 교사가 문항·정답·풀이를 확인해야 합니다.

### 네트워크 및 재시도
- API 호출은 기본 1회입니다. 동일 요청을 자동으로 반복하지 않습니다.
- 요청 시간 제한은 90초입니다.
- 생성 출력은 5,000 토큰으로 제한해 지나치게 긴 응답을 방지합니다.
- 스트리밍 미지원 환경에서는 비스트리밍 SDK 호출로 호환 처리합니다.

### 업데이트 적용
기존 GitHub 저장소의 `app.py`, `engine.py`, `README.md`를 이 배포판 파일로 교체하고, `data/` 폴더와 `requirements.txt`는 그대로 유지해도 됩니다. 가장 간단한 방법은 ZIP을 압축 해제하고 프로젝트 전체를 저장소 최상위에 덮어 업로드하는 것입니다.

실제 Streamlit Cloud에서의 첫 토큰 도착 시간과 전체 생성 시간은 계정 요금제, API 지역·할당량, 모델 부하, 선택 성취기준, 사용자 추가 지시문에 따라 달라집니다. 이 패키지의 모의 테스트는 실제 API 지연 시간을 측정하지 않습니다.
