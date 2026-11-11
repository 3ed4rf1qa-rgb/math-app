from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import jsonschema
except ImportError:
    jsonschema = None


class DataIntegrityError(RuntimeError):
    """필수 교육과정/지식 데이터의 연결이 깨졌을 때 발생."""


class GenerationError(RuntimeError):
    """AI 생성 또는 결과 검증 실패."""


class KnowledgeStore:
    """공식 성취기준과 프로젝트 지식 데이터를 한 번에 조회하는 저장소."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.standards = self._load("achievement_standards.json")["standards"]
        self.concepts = self._load("all_concepts.json")["concepts"]
        self.misconceptions = self._load("all_misconceptions.json")["misconceptions"]
        self.activities = self._load("all_inquiry_activities.json")["activities"]
        self.blueprints = self._load("all_item_blueprints.json")["item_blueprints"]
        self.standard_map = self._load("all_standard_concept_map.json")["mappings"]
        self.scope_data = self._load("all_scope_guardrails.json")["courses"]
        self.guidance_areas = self._load("area_guidance.json")["areas"]
        self.principles = self._load("design_principles.json")["principles"]
        self.relations = self._load("concept_relations.json")["relations"]
        self.package_schema = self._load("assessment_package.schema.json")
        self.generation_schema = self._load("gemini_generation.schema.json")

        self._concept_by_id = {x["id"]: x for x in self.concepts}
        self._activity_by_concept: dict[str, list[dict[str, Any]]] = {}
        self._misconception_by_concept: dict[str, list[dict[str, Any]]] = {}
        self._blueprint_by_concept: dict[str, list[dict[str, Any]]] = {}
        self._mapping_by_code = {x["standard_code"]: x for x in self.standard_map}
        self._guardrail_by_course = {
            x.get("metadata", {}).get("course_id"): x for x in self.scope_data
        }
        self._guidance_by_id = {x["id"]: x for x in self.guidance_areas}
        self._principle_by_id = {x["id"]: x for x in self.principles}
        self._standard_by_code = {x["code"]: x for x in self.standards}

        for record in self.activities:
            self._activity_by_concept.setdefault(record["concept_id"], []).append(record)
        for record in self.misconceptions:
            self._misconception_by_concept.setdefault(record["concept_id"], []).append(record)
        for record in self.blueprints:
            self._blueprint_by_concept.setdefault(record["concept_id"], []).append(record)

    def _load(self, filename: str) -> dict[str, Any]:
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"지식 데이터 파일이 없습니다: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DataIntegrityError(f"JSON 파싱 실패: {filename}: {exc}") from exc

    def list_courses(self) -> list[dict[str, str]]:
        seen: dict[str, dict[str, str]] = {}
        for standard in self.standards:
            seen.setdefault(
                standard["course_id"],
                {
                    "course_id": standard["course_id"],
                    "course_name": standard["course_name"],
                    "course_category": standard["course_category"],
                },
            )
        return list(seen.values())

    def list_standards(self, course_id: str, unit_id: Optional[str] = None) -> list[dict[str, Any]]:
        rows = [x for x in self.standards if x["course_id"] == course_id]
        if unit_id:
            rows = [x for x in rows if x["unit_id"] == unit_id]
        return rows

    def list_units(self, course_id: str) -> list[dict[str, str]]:
        seen: dict[str, dict[str, str]] = {}
        for standard in self.list_standards(course_id):
            seen.setdefault(
                standard["unit_id"],
                {"unit_id": standard["unit_id"], "unit_name": standard["unit_name"]},
            )
        return list(seen.values())

    def build_context(self, course_id: str, standard_code: str) -> dict[str, Any]:
        standard = self._standard_by_code.get(standard_code)
        if not standard:
            raise KeyError(f"공식 성취기준 코드를 찾을 수 없습니다: {standard_code}")
        if standard["course_id"] != course_id:
            raise ValueError(
                f"선택 과목({course_id})과 성취기준 과목({standard['course_id']})이 일치하지 않습니다."
            )

        mapping = self._mapping_by_code.get(standard_code)
        if not mapping:
            raise DataIntegrityError(f"성취기준-개념 연결표에 코드가 없습니다: {standard_code}")

        concept_ids = mapping.get("concept_ids", [])
        concepts = [self._concept_by_id[x] for x in concept_ids if x in self._concept_by_id]
        missing_concepts = sorted(set(concept_ids) - set(self._concept_by_id))
        if missing_concepts:
            raise DataIntegrityError(f"연결된 개념 ID가 존재하지 않습니다: {missing_concepts}")
        if not concepts:
            # Some historical concept records link via standard_codes rather than mapping rows.
            concepts = [
                c for c in self.concepts
                if standard_code in c.get("standard_codes", [])
                and c["course_id"] == course_id
            ]
        if not concepts:
            raise DataIntegrityError(f"성취기준과 연결된 개념이 없습니다: {standard_code}")

        concept_ids = [x["id"] for x in concepts]
        activities = [
            activity
            for concept_id in concept_ids
            for activity in self._activity_by_concept.get(concept_id, [])
        ]
        misconceptions = [
            item
            for concept_id in concept_ids
            for item in self._misconception_by_concept.get(concept_id, [])
        ]
        blueprints = [
            item
            for concept_id in concept_ids
            for item in self._blueprint_by_concept.get(concept_id, [])
        ]
        guardrails = self._guardrail_by_course.get(course_id, {})
        guidance_id = standard.get("guidance_id")
        guidance = self._guidance_by_id.get(guidance_id, {}) if guidance_id else {}

        if not activities:
            raise DataIntegrityError(f"연결된 탐구 활동이 없습니다: {standard_code}")
        if not blueprints:
            raise DataIntegrityError(f"연결된 문항 설계 템플릿이 없습니다: {standard_code}")

        return {
            "standard": standard,
            "mapping": mapping,
            "concepts": concepts,
            "activities": activities,
            "misconceptions": misconceptions,
            "blueprints": blueprints,
            "guardrails": guardrails,
            "area_guidance": guidance,
            "principles": self.principles,
        }


def _first_nonempty(values: list[dict[str, Any]], key: str, fallback: str) -> str:
    for value in values:
        text = value.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return fallback


def build_offline_scaffold(context: dict[str, Any]) -> dict[str, Any]:
    """API 키 없이도 전체 입력-조회-패키징 흐름을 확인할 수 있는 초안."""
    standard = context["standard"]
    concepts = context["concepts"]
    activities = context["activities"]
    misconceptions = context["misconceptions"]
    blueprints = context["blueprints"]

    activity = activities[0]
    blueprint = blueprints[0]
    concept_names = [x["name"] for x in concepts]
    selected_principles = context["principles"][:4]

    design = {
        "principle_ids": [x["id"] for x in selected_principles],
        "context": (
            f"{standard['unit_name']}에서 {concept_names[0]} 개념이 필요한 수학적 상황을 교사가 선택한다. "
            "이 초안은 상황의 조건과 수치를 아직 확정하지 않은 설계 단계다."
        ),
        "driving_question": activity.get("driving_question") or f"{concept_names[0]}의 의미와 성질을 어떻게 설명할 수 있을까?",
        "learning_objectives": [
            f"{concept_names[0]}의 핵심 의미와 성질을 설명한다.",
            f"{standard['content']}를 해결하는 데 필요한 수학적 표현과 근거를 제시한다."
        ],
        "inquiry_steps": [
            {"phase": f"탐구 {i+1}", "teacher_action": step, "student_evidence": (activity.get("evidence") or ["관찰·계산 기록"])[min(i, len(activity.get("evidence") or ["관찰·계산 기록"])-1)]}
            for i, step in enumerate(activity.get("steps", [])[:4])
        ],
        "representations": list(dict.fromkeys(
            (
                [x.strip() for x in activity.get("suggested_tools", "").split(",") if x.strip()]
                if isinstance(activity.get("suggested_tools", ""), str)
                else [str(x).strip() for x in (activity.get("suggested_tools") or []) if str(x).strip()]
            )
            + ["수식", "표 또는 그래프", "학생의 언어적 설명"]
        )),
        "misconception_support": [
            {
                "misconception_id": x["id"],
                "diagnostic_question": x.get("diagnostic_prompt", "이 개념을 어떤 근거로 판단했는가?"),
                "corrective_feedback": x.get("corrective_feedback", "조건을 다시 확인하고 다른 표현으로 설명해 보자.")
            }
            for x in misconceptions[:3]
        ],
        "differentiation": {
            "support": ["핵심 용어와 기호를 확인할 수 있는 짧은 예제를 먼저 제공한다.", "표·그래프·수식 중 한 가지 표현을 선택해 설명하게 한다."],
            "extension": ["조건을 하나 바꾸어 결론이 유지되는지 검토한다.", "서로 다른 표현 사이의 관계를 설명하게 한다."]
        }
    }
    item = {
        "item_type": blueprint.get("item_type", "서술형"),
        "cognitive_demand": blueprint.get("cognitive_demand", "이해"),
        "prompt": (
            f"[교사/AI 구체화 필요] {standard['content']}를 평가하도록 "
            f"{concept_names[0]}와 관련된 조건·자료를 설정하고, 학생이 계산 또는 추론 과정과 근거를 설명하도록 문항을 완성한다."
        ),
        "expected_answer": "오프라인 설계 초안에서는 정답을 자동 확정하지 않는다. 실제 조건과 수치를 정한 뒤 모범답안을 작성해야 한다.",
        "solution_steps": [
            "성취기준과 연결 개념에서 필요한 조건과 수치를 먼저 정한다.",
            "정의·성질·계산 절차를 사용해 해결 과정을 구성한다.",
            "결론이 주어진 조건을 만족하는지 검산하고 해석한다."
        ],
        "rubric": {
            "total_points": 10,
            "criteria": [
                {"criterion": "개념 및 조건 이해", "points": 3, "levels": {k: f"{k} 수준의 개념 이해 증거를 교사가 구체화해야 함" for k in "ABCDE"}},
                {"criterion": "수학적 절차와 추론", "points": 4, "levels": {k: f"{k} 수준의 절차·추론 증거를 교사가 구체화해야 함" for k in "ABCDE"}},
                {"criterion": "표현과 근거 제시", "points": 3, "levels": {k: f"{k} 수준의 표현·근거 증거를 교사가 구체화해야 함" for k in "ABCDE"}}
            ]
        }
    }
    formative = {
        "questions": [
            f"{concept_names[0]}의 핵심 정의 또는 성질을 자신의 말로 설명할 수 있는가?",
            "풀이에서 사용한 조건과 근거를 구분해 말할 수 있는가?"
        ],
        "success_criteria": ["핵심 개념을 정확히 사용한다.", "풀이 절차와 결론 사이의 근거를 제시한다."]
    }
    return {"design": design, "item": item, "formative_check": formative, "_mode": "offline_scaffold"}


def build_generation_prompt(
    context: dict[str, Any],
    user_requirements: Optional[str] = None,
) -> str:
    """Build a compact, curriculum-grounded prompt for a single-pass response."""
    standard = context["standard"]
    compact_concepts = [
        {
            "id": c["id"],
            "name": c["name"],
            "definition": str(c.get("definition", ""))[:700],
            "formulas": c.get("formulas", [])[:5],
            "properties": c.get("key_properties", [])[:5],
            "standard_codes": c.get("standard_codes", []),
        }
        for c in context["concepts"][:5]
    ]
    compact_activities = [
        {
            "id": a["id"],
            "title": a.get("title"),
            "driving_question": a.get("driving_question"),
            "steps": a.get("steps", [])[:4],
            "evidence": a.get("evidence", [])[:3],
            "suggested_tools": a.get("suggested_tools"),
        }
        for a in context["activities"][:3]
    ]
    compact_misconceptions = [
        {
            "id": m["id"],
            "concept_id": m["concept_id"],
            "misconception": m.get("misconception"),
            "diagnostic_prompt": m.get("diagnostic_prompt"),
            "corrective_feedback": m.get("corrective_feedback"),
        }
        for m in context["misconceptions"][:5]
    ]
    compact_blueprints = [
        {
            "id": b["id"],
            "item_type": b.get("item_type"),
            "cognitive_demand": b.get("cognitive_demand"),
            "expected_evidence": b.get("expected_evidence"),
            "scoring_dimensions": b.get("scoring_dimensions"),
        }
        for b in context["blueprints"][:3]
    ]
    guardrails = context["guardrails"]
    guidance = context["area_guidance"]
    # Use the most directly relevant principles. All 12 remain in the local
    # validation database; only six are sent to reduce prompt overhead.
    priority_ids = {"DP01", "DP02", "DP03", "DP05", "DP07", "DP08"}
    principles = [
        {
            "id": p["id"],
            "name": p["name"],
            "implementation": p.get("implementation", ""),
            "quality_checks": p.get("quality_checks", [])[:2],
        }
        for p in context["principles"]
        if p.get("id") in priority_ids
    ]
    packed = {
        "official_standard": {
            "course": standard["course_name"],
            "unit": standard["unit_name"],
            "code": standard["code"],
            "content": standard["content"],
        },
        "concepts": compact_concepts,
        "inquiry_activities": compact_activities,
        "misconceptions": compact_misconceptions,
        "item_blueprints": compact_blueprints,
        "course_scope_guardrails": {
            "allowed_core": guardrails.get("allowed_core", []),
            "avoid_or_limit": guardrails.get("avoid_or_limit", []),
            "nuance_notes": guardrails.get("nuance_notes", []),
        },
        "unit_application_guidance": guidance.get("ai_generation_guardrails_summary", ""),
        "original_design_principles": principles,
        "teacher_requirements": (user_requirements or "")[:1200],
    }
    return f"""
당신은 2022 개정 고등학교 수학 교육과정에 기반한 탐구 수업 및 서·논술형 평가 설계자다.
입력 자료에 없는 성취기준이나 개념 범위를 창작하지 않는다.

[작업]
선택한 성취기준 한 개에 대한 수업 1개, 평가 문항 1개, 형성평가를 한 번에 완성한다.
관찰·조작·추측·검증·설명이 드러나야 하며, 단순 문제 나열은 금지한다.

[필수 품질 규칙]
1. 성취기준 코드와 원문을 정확히 유지한다: {standard['code']} — {standard['content']}
2. 과목 범위와 제한사항을 지키고 상위 과목의 절차를 가져오지 않는다.
3. 탐구 단계는 4~5개로 구성하고 예측/관찰/조작/분석/정리/적용 중 최소 3단계를 포함한다.
4. 실제 조건과 수치가 있는 완결 문항을 만든다. 빈칸·플레이스홀더·교사에게 조건을 채우라는 표현은 금지한다.
5. 정답과 풀이를 계산·논리적으로 일치시킨다.
6. 채점기준은 평가요소 3개, 총 10점으로 하고 각 요소에 A~E의 구별되는 관찰 가능한 수행기술을 작성한다.
7. 오개념은 단정하지 말고 진단 질문과 교정 피드백으로 다룬다.
8. 출력은 간결하되 교사가 바로 편집할 수 있을 만큼 구체적으로 작성한다.
9. 저작권이 있는 교과서 문장·문항·그림이나 특정 출판사 자료를 복제하지 않는다.
10. 결과는 교사 검토가 필요한 자동 생성 초안임을 전제로 한다.

[분량 기준]
- 수업 단계 4~5개, 학습목표 2~3개, 표현 방법 2~3개
- 오개념 지원 최대 3개, 차별화 지원·확장 각각 2개 이내
- 문항 풀이 3~5단계, 형성평가 질문 2~3개
- 평가요소 3개, A~E 기술은 각 1~2문장으로 간결하게

[교육과정 근거 데이터]
{json.dumps(packed, ensure_ascii=False, separators=(',', ':'))}

지정된 JSON 응답 스키마에 맞춰 design, item, formative_check 세 부분만 반환한다.
""".strip()


def _make_selection(context: dict[str, Any]) -> dict[str, Any]:
    s = context["standard"]
    return {
        "course_id": s["course_id"],
        "course_name": s["course_name"],
        "unit_id": s["unit_id"],
        "unit_name": s["unit_name"],
        "standard_code": s["code"],
        "standard_content": s["content"],
        "concept_ids": [x["id"] for x in context["concepts"]],
        "concept_names": [x["name"] for x in context["concepts"]],
        "official_source": s.get("source")
    }


def _run_checks(package: dict[str, Any], context: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    def add(name: str, ok: bool, detail: str, blocking: bool = True):
        status = "PASS" if ok else ("FAIL" if blocking else "WARN")
        checks.append({"name": name, "status": status, "detail": detail})
        if not ok:
            (errors if blocking else warnings).append(detail)

    if jsonschema:
        try:
            jsonschema.validate(package, schema)
            add("package_schema", True, "최종 패키지가 JSON Schema 구조를 만족한다.")
        except jsonschema.ValidationError as exc:
            add("package_schema", False, f"JSON Schema 오류: {exc.message}")
    else:
        add("package_schema", False, "jsonschema 패키지가 설치되지 않았다.")

    selection = package.get("selection", {})
    standard = context["standard"]
    add("official_standard_binding",
        selection.get("standard_code") == standard["code"] and selection.get("standard_content") == standard["content"],
        "선택된 성취기준 코드와 본문이 공식 데이터와 일치한다.")
    add("course_binding",
        selection.get("course_id") == standard["course_id"] and selection.get("unit_id") == standard["unit_id"],
        "과목 및 단원 ID가 공식 성취기준 레코드와 일치한다.")

    allowed_concepts = {x["id"] for x in context["concepts"]}
    used_concepts = set(selection.get("concept_ids", []))
    add("concept_references", bool(used_concepts) and used_concepts.issubset(allowed_concepts),
        "패키지의 개념 ID가 선택 성취기준에 연결된 지식 데이터에 존재한다.")

    principle_ids = {x["id"] for x in context["principles"]}
    used_principles = set(package.get("design", {}).get("principle_ids", []))
    add("design_principle_references", bool(used_principles) and used_principles.issubset(principle_ids),
        "사용한 교수설계 원칙 ID가 5단계 데이터베이스에 존재한다.")

    rubric = package.get("item", {}).get("rubric", {})
    criteria = rubric.get("criteria", [])
    points = sum(int(x.get("points", 0)) for x in criteria)
    add("rubric_points", points == rubric.get("total_points") == 10,
        f"채점기준 배점 합계 {points}점 / 설정 총점 {rubric.get('total_points')}점 (10점 기준).")
    level_ok = bool(criteria) and all(set(c.get("levels", {}).keys()) == set("ABCDE") for c in criteria)
    add("rubric_levels", level_ok, "모든 평가요소에 A·B·C·D·E 수준 기술이 존재한다.")

    item = package.get("item", {})
    complete = all(str(item.get(k, "")).strip() for k in ["prompt", "expected_answer"]) and bool(item.get("solution_steps"))
    is_scaffold = package.get("metadata", {}).get("generation_mode") == "offline_scaffold"
    add("item_completeness", complete and not is_scaffold,
        "문항·정답·풀이가 모두 작성되어 있다." if complete and not is_scaffold else "오프라인 설계 초안 또는 문항 미완성 상태다.",
        blocking=not is_scaffold)
    if is_scaffold:
        warnings.append("오프라인 초안에는 완결된 문항과 정답이 없다. Gemini 생성 또는 교사 작성 후 사용해야 한다.")

    warnings.append("수학적 정답·풀이의 완전한 타당성은 자동 구조 검사만으로 증명되지 않는다. 교사 검토가 필요하다.")
    warnings.append("개념 연결과 오개념 진단 데이터는 프로젝트가 작성한 교수설계 초안이며 전문가 검토 상태는 pending이다.")

    return {
        "status": "BLOCKED" if errors else ("SCAFFOLD_ONLY" if is_scaffold else "PASS_WITH_TEACHER_REVIEW"),
        "checks": checks,
        "blocking_errors": errors,
        "warnings": warnings
    }


def assemble_package(context: dict[str, Any], generated: dict[str, Any], mode: str, model: Optional[str] = None) -> dict[str, Any]:
    package = {
        "metadata": {
            "package_id": str(uuid.uuid4()),
            "generation_mode": mode,
            "model": model,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "teacher_review_required": True
        },
        "selection": _make_selection(context),
        "design": generated["design"],
        "item": generated["item"],
        "formative_check": generated["formative_check"],
        "validation": {}
    }
    package["validation"] = _run_checks(package, context, _SCHEMA_CACHE["package_schema"])
    return package


_SCHEMA_CACHE: dict[str, Any] = {}


def generate_with_client(
    context: dict[str, Any],
    client: Any,
    model: str = "gemini-3.8-flash",
    user_requirements: Optional[str] = None,
    thinking_level: str = "low",
    max_attempts: int = 1,
    on_chunk: Optional[Any] = None,
) -> dict[str, Any]:
    """Structured generation with token streaming when supported by the SDK."""
    prompt = build_generation_prompt(context, user_requirements)
    schema = _SCHEMA_CACHE.get("generation_schema")
    if schema is None:
        raise DataIntegrityError("Gemini 생성 스키마가 초기화되지 않았다.")
    if thinking_level not in {"minimal", "low", "medium", "high"}:
        raise ValueError("thinking_level은 minimal, low, medium, high 중 하나여야 한다.")

    config = {
        "response_mime_type": "application/json",
        "response_json_schema": schema,
        "thinking_config": {"thinking_level": thinking_level},
        "max_output_tokens": 5000,
    }
    last_error: Optional[Exception] = None
    attempts = max(1, int(max_attempts))
    for attempt in range(attempts):
        try:
            models = client.models
            stream_method = getattr(models, "generate_content_stream", None)
            if callable(stream_method):
                parts: list[str] = []
                for chunk in stream_method(model=model, contents=prompt, config=config):
                    chunk_text = getattr(chunk, "text", None)
                    if chunk_text:
                        parts.append(chunk_text)
                        if on_chunk:
                            on_chunk("".join(parts))
                raw = "".join(parts)
                if not raw:
                    raise GenerationError(
                        "Gemini 스트리밍 응답이 비어 있다. 모델 제한 또는 응답 차단 여부를 확인해야 한다."
                    )
            else:
                # Compatibility path for test doubles and older SDK adapters.
                response = models.generate_content(
                    model=model, contents=prompt, config=config
                )
                raw = getattr(response, "text", None)
                if not raw and getattr(response, "parsed", None) is not None:
                    parsed = response.parsed
                    raw = (
                        parsed.model_dump_json()
                        if hasattr(parsed, "model_dump_json")
                        else json.dumps(parsed, ensure_ascii=False)
                    )
            if not raw:
                raise GenerationError("Gemini 응답 본문이 비어 있다.")
            result = json.loads(raw)
            if jsonschema:
                jsonschema.validate(result, schema)
            return result
        except Exception as exc:
            last_error = exc
            text_error = str(exc).lower()
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            retryable = (
                code in {429, 500, 502, 503, 504}
                or any(token in text_error for token in (
                    "resource_exhausted", "service_unavailable", "internal error",
                    "temporarily unavailable", "deadline_exceeded"
                ))
            )
            # Default is one request. Retries remain opt-in for transient errors.
            if not retryable or attempt + 1 >= attempts:
                break
            time.sleep(0.5)
    raise GenerationError(f"Gemini 생성 실패: {last_error}") from last_error

def generate_with_gemini(
    context: dict[str, Any],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    user_requirements: Optional[str] = None,
    thinking_level: str = "low",
    on_chunk: Optional[Any] = None,
) -> dict[str, Any]:
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise GenerationError("GEMINI_API_KEY가 없다. Streamlit Secrets 또는 앱 입력란에 API 키를 설정해야 한다.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise GenerationError("google-genai 패키지가 설치되지 않았다. requirements.txt를 설치해야 한다.") from exc

    # Bound a stalled request and disable the SDK's opaque multi-retry loop.
    # A normal request therefore means one Gemini generation call.
    http_options = types.HttpOptions(
        timeout=90_000,
        retry_options=types.HttpRetryOptions(attempts=1),
    )
    client = genai.Client(api_key=key, http_options=http_options)
    try:
        return generate_with_client(
            context,
            client,
            model=model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            user_requirements=user_requirements,
            thinking_level=thinking_level,
            max_attempts=1,
            on_chunk=on_chunk,
        )
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def generate_package(store: KnowledgeStore, course_id: str, standard_code: str,
                     mode: str = "offline", api_key: Optional[str] = None,
                     model: Optional[str] = None, user_requirements: Optional[str] = None,
                     thinking_level: str = "low",
                     on_chunk: Optional[Any] = None) -> dict[str, Any]:
    context = store.build_context(course_id, standard_code)
    if mode == "offline":
        generated = build_offline_scaffold(context)
        actual_mode = "offline_scaffold"
    elif mode == "gemini":
        generated = generate_with_gemini(
            context, api_key, model, user_requirements, thinking_level, on_chunk=on_chunk
        )
        actual_mode = "gemini_structured"
    else:
        raise ValueError("mode는 'offline' 또는 'gemini'만 사용할 수 있다.")

    _SCHEMA_CACHE["generation_schema"] = store.generation_schema
    _SCHEMA_CACHE["package_schema"] = store.package_schema

    package = assemble_package(context, generated, actual_mode, model if mode == "gemini" else None)
    # Re-run full package schema with the actual store schema.
    package["validation"] = _run_checks(package, context, store.package_schema)
    if package["validation"]["blocking_errors"]:
        raise GenerationError("생성 패키지 검증 실패: " + " | ".join(package["validation"]["blocking_errors"]))
    return package


def validate_package_against_store(store: KnowledgeStore, package: dict[str, Any]) -> dict[str, Any]:
    code = package.get("selection", {}).get("standard_code")
    course_id = package.get("selection", {}).get("course_id")
    context = store.build_context(course_id, code)
    result = _run_checks(package, context, store.package_schema)
    if package.get("metadata", {}).get("generation_mode") == "offline_scaffold":
        result["status"] = "SCAFFOLD_ONLY"
    return result


def create_store(data_dir: str | Path) -> KnowledgeStore:
    store = KnowledgeStore(data_dir)
    _SCHEMA_CACHE["generation_schema"] = store.generation_schema
    _SCHEMA_CACHE["package_schema"] = store.package_schema
    return store
