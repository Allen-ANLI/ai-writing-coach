"""LangGraph workflow definitions (SD §9).

Only genuinely multi-step, stateful, human-confirmed flows live here.
Graph-level checkpointing uses an in-process MemorySaver; durable pause/resume
is provided by the business-state rows in PostgreSQL (ADR-020), so a restart
never loses an awaiting-confirmation workflow.
"""

import uuid
from collections.abc import Callable
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import sessionmaker

from app.ai import llm
from app.ai.prompts.registry import get_prompt
from app.ai.schemas import ExtractionResult, OutlineGenerationResult, StudyPlanResult
from app.modules.essays.models import Essay, EssayVersion
from app.modules.expressions import knowledge
from app.modules.learning import service as learning_service
from app.modules.users.models import User

Emit = Callable[[str, str, dict], None]


class PlannerState(TypedDict, total=False):
    question_prompt: str
    viewpoint: str
    instructions: str
    previously_learned: str
    outline: dict | None
    quality_ok: bool
    retries: int
    error: str | None


class ExtractorState(TypedDict, total=False):
    essay_text: str
    scope: str
    candidates: list[dict]
    error: str | None


class StudyPlannerState(TypedDict, total=False):
    weakness_profile: str
    mastery_summary: str
    practice_summary: str
    goal: str
    plan: dict | None
    error: str | None


def _planner_graph(session_factory: sessionmaker, user_id: uuid.UUID, emit: Emit):
    def retrieve_expressions(state: PlannerState) -> dict:
        emit("retrieve_expressions", "step_started", {})
        with session_factory() as db:
            recalled = knowledge.semantic_candidates(
                db, user_id, state.get("viewpoint") or state.get("question_prompt", ""), limit=5
            )
            learned = "; ".join(e.english_text for e in recalled) or "(none)"
        emit("retrieve_expressions", "step_completed", {"count": len(recalled)})
        return {"previously_learned": learned}

    def generate_outline(state: PlannerState) -> dict:
        emit("generate_outline", "step_started", {})
        prompt = get_prompt("outline_generate", "v1")
        user_message = prompt.user_template.format(
            question_prompt=state.get("question_prompt", "(free writing)"),
            viewpoint=state.get("viewpoint") or "(not provided)",
            instructions=state.get("instructions") or "(none)",
            previously_learned=state.get("previously_learned", "(none)"),
        )
        result, usage = llm.call_llm(
            system=prompt.system, user=user_message, response_model=OutlineGenerationResult
        )
        emit("generate_outline", "step_completed", {"sections": len(result.sections)})
        return {"outline": result.model_dump()}

    def quality_check(state: PlannerState) -> dict:
        emit("quality_check", "step_started", {})
        outline = state.get("outline") or {}
        sections = outline.get("sections", [])
        ok = (
            len(sections) >= 2
            and bool(outline.get("thesis_statement"))
            and all(
                paragraph.get("sentence_ideas")
                for section in sections
                for paragraph in section.get("paragraphs", [])
            )
        )
        emit("quality_check", "step_completed", {"quality_ok": ok})
        return {"quality_ok": ok, "retries": state.get("retries", 0) + 1}

    def route_after_quality(state: PlannerState) -> str:
        if state.get("quality_ok") or state.get("retries", 0) >= 2:
            return END
        return "generate_outline"

    graph = StateGraph(PlannerState)
    graph.add_node("retrieve_expressions", retrieve_expressions)
    graph.add_node("generate_outline", generate_outline)
    graph.add_node("quality_check", quality_check)
    graph.set_entry_point("retrieve_expressions")
    graph.add_edge("retrieve_expressions", "generate_outline")
    graph.add_edge("generate_outline", "quality_check")
    graph.add_conditional_edges("quality_check", route_after_quality)
    return graph.compile(checkpointer=MemorySaver())


def _extractor_graph(emit: Emit):
    def extract(state: ExtractorState) -> dict:
        emit("extract", "step_started", {})
        prompt = get_prompt("learning_extract", "v1")
        user_message = prompt.user_template.format(
            scope=state.get("scope", "full"), essay_text=state.get("essay_text", "")
        )
        result, usage = llm.call_llm(
            system=prompt.system, user=user_message, response_model=ExtractionResult
        )
        emit("extract", "step_completed", {"candidates": len(result.candidates)})
        return {"candidates": [candidate.model_dump() for candidate in result.candidates]}

    def dedupe(state: ExtractorState) -> dict:
        emit("dedupe", "step_started", {})
        seen: set[str] = set()
        unique: list[dict] = []
        for candidate in state.get("candidates", []):
            key = candidate["english_text"].strip().lower()
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        emit("dedupe", "step_completed", {"candidates": len(unique)})
        return {"candidates": unique}

    graph = StateGraph(ExtractorState)
    graph.add_node("extract", extract)
    graph.add_node("dedupe", dedupe)
    graph.set_entry_point("extract")
    graph.add_edge("extract", "dedupe")
    graph.add_edge("dedupe", END)
    return graph.compile(checkpointer=MemorySaver())


def _study_planner_graph(session_factory: sessionmaker, user_id: uuid.UUID, emit: Emit):
    def gather_context(state: StudyPlannerState) -> dict:
        emit("gather_context", "step_started", {})
        with session_factory() as db:
            user = db.get(User, user_id)
            weaknesses = learning_service.list_weaknesses(db, user)
            summary = learning_service.learning_summary(db, user)
        weakness_profile = (
            "; ".join(
                f"{w.category}/{w.sub_category or '-'}: {w.total_occurrences}"
                for w in weaknesses[:8]
            )
            or "(no recorded weaknesses)"
        )
        mastery_summary = (
            f"total={summary['total_expressions']}, mastered={summary['mastered']}, "
            f"due_now={summary['due_now']}, reviewed_today={summary['reviewed_today']}"
        )
        emit("gather_context", "step_completed", {})
        return {
            "weakness_profile": weakness_profile,
            "mastery_summary": mastery_summary,
            "practice_summary": state.get("practice_summary", "(not provided)"),
        }

    def generate_plan(state: StudyPlannerState) -> dict:
        emit("generate_plan", "step_started", {})
        prompt = get_prompt("study_plan", "v1")
        user_message = prompt.user_template.format(
            weakness_profile=state.get("weakness_profile", "(none)"),
            mastery_summary=state.get("mastery_summary", "(none)"),
            practice_summary=state.get("practice_summary", "(none)"),
            goal=state.get("goal") or "(not provided)",
        )
        result, usage = llm.call_llm(
            system=prompt.system, user=user_message, response_model=StudyPlanResult
        )
        emit("generate_plan", "step_completed", {"suggestions": len(result.suggestions)})
        return {"plan": result.model_dump()}

    graph = StateGraph(StudyPlannerState)
    graph.add_node("gather_context", gather_context)
    graph.add_node("generate_plan", generate_plan)
    graph.set_entry_point("gather_context")
    graph.add_edge("gather_context", "generate_plan")
    graph.add_edge("generate_plan", END)
    return graph.compile(checkpointer=MemorySaver())


def build_graph(workflow_type: str, session_factory: sessionmaker, user_id: uuid.UUID, emit: Emit):
    if workflow_type == "writing_planner":
        return _planner_graph(session_factory, user_id, emit)
    if workflow_type == "learning_extractor":
        return _extractor_graph(emit)
    if workflow_type == "personalized_study_planner":
        return _study_planner_graph(session_factory, user_id, emit)
    raise ValueError(f"Unknown workflow type: {workflow_type}")


def initial_state(
    workflow_type: str, input_json: dict, essay: Essay | None, version: EssayVersion | None
) -> dict:
    if workflow_type == "writing_planner":
        return {
            "question_prompt": (essay.question_prompt if essay else None)
            or input_json.get("question_prompt")
            or "(free writing)",
            "viewpoint": input_json.get("viewpoint", ""),
            "instructions": input_json.get("instructions", ""),
            "retries": 0,
        }
    if workflow_type == "learning_extractor":
        return {
            "essay_text": version.plain_text if version else "",
            "scope": input_json.get("scope", "full"),
        }
    return {
        "goal": input_json.get("goal", ""),
        "practice_summary": input_json.get("practice_summary", ""),
    }


def result_payload(workflow_type: str, state: dict) -> dict:
    if workflow_type == "writing_planner":
        return {"outline": state.get("outline")}
    if workflow_type == "learning_extractor":
        return {"candidates": state.get("candidates", [])}
    return {"plan": state.get("plan")}
