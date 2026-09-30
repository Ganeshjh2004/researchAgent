"""
research_workflow.py
────────────────────
Multi-step research workflow using LangGraph StateGraph.

Workflow:
  validate_input → research → validate_research
       → synthesize → validate_output → save_report → final_response

Usage:
  python research_workflow.py
  or import run_research_workflow() from another module.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

# ── project-local imports ─────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from tools import save_to_txt, search_tool, wiki_tool  # configured instances

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("research_workflow")

# ── LLM ───────────────────────────────────────────────────────────────────────
_GROQ_KEY = os.getenv("GROQ_API_KEY")
if not _GROQ_KEY:
    raise EnvironmentError("GROQ_API_KEY not found. Check your .env file.")

llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0)

REDIS_URI = "redis://localhost:6379"

# ── Workflow State ─────────────────────────────────────────────────────────────

class WorkflowState(TypedDict, total=False):
    # Input
    user_request: str
    research_query: str
    output_filename: str

    # Research outputs
    research_results: str          # raw concatenated text from tools
    research_sources: list         # source identifiers (tool names used)

    # Synthesis outputs
    synthesized_report: str

    # Control
    error: Optional[str]
    execution_status: str          # "running" | "failed" | "complete"
    validation_passed: bool

    # Final
    final_response: str
    save_status: str


# ── helpers ───────────────────────────────────────────────────────────────────

def _safe_filename(name: str) -> str:
    """Strip unsafe path characters and enforce .txt extension."""
    name = re.sub(r"[^\w\-. ]", "_", name).strip()
    name = name.replace(" ", "_")
    if not name.endswith(".txt"):
        name += ".txt"
    # Guard against path traversal
    return Path(name).name


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── Node 1: validate_input ────────────────────────────────────────────────────

def validate_input(state: WorkflowState) -> WorkflowState:
    log.info("NODE: validate_input")
    request = (state.get("user_request") or "").strip()

    if not request:
        log.warning("Empty user_request received.")
        return {
            **state,
            "error": "User request is empty. Please provide a research topic.",
            "execution_status": "failed",
        }

    # Derive a focused search query
    query = request
    for prefix in ("research", "search for", "find out about", "look up"):
        if query.lower().startswith(prefix):
            query = query[len(prefix):].strip()
            break

    # Build a safe unique output filename
    slug = re.sub(r"[^\w\s]", "", query)[:40].strip().replace(" ", "_").lower()
    filename = f"research_{slug}_{_stamp()}.txt"

    log.info("Research query derived: %s", query)
    log.info("Output filename: %s", filename)

    return {
        **state,
        "research_query": query,
        "output_filename": filename,
        "execution_status": "running",
        "error": None,
    }


# ── Node 2: research ──────────────────────────────────────────────────────────

def research(state: WorkflowState) -> WorkflowState:
    log.info("NODE: research")
    query = state.get("research_query", "")

    if not query:
        return {
            **state,
            "error": "No research query available.",
            "execution_status": "failed",
        }

    collected = []
    sources = []  # list of {name: str, url: str|None}

    # Tool 1 — DuckDuckGo (structured results with title, snippet, link)
    try:
        log.info("Calling DuckDuckGo for: %s", query)
        ddg_results = search_tool.invoke(query)

        # ddg_results is a list of dicts: [{snippet, title, link}, ...]
        if isinstance(ddg_results, list) and ddg_results:
            # Build human-readable text for the synthesis prompt
            ddg_text_parts = []
            for item in ddg_results:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                ddg_text_parts.append(f"- {title}: {snippet}")
                # Collect as a structured source with URL
                if title or link:
                    sources.append({"name": title or "DuckDuckGo result", "url": link or None})
            collected.append("[DuckDuckGo]\n" + "\n".join(ddg_text_parts))
            log.info("DuckDuckGo returned %d results.", len(ddg_results))
        elif isinstance(ddg_results, str) and ddg_results.strip():
            # Fallback: if tool returns a plain string (unexpected but safe)
            collected.append("[DuckDuckGo]\n" + ddg_results.strip())
            sources.append({"name": "DuckDuckGo", "url": None})
            log.info("DuckDuckGo returned %d chars (string fallback).", len(ddg_results))
        else:
            log.warning("DuckDuckGo returned empty result.")
    except Exception as exc:
        log.warning("DuckDuckGo failed: %s", exc)

    # Tool 2 — Wikipedia (plain text — no structured URLs available)
    try:
        log.info("Calling Wikipedia for: %s", query)
        wiki_result = wiki_tool.invoke(query)
        if wiki_result and wiki_result.strip():
            collected.append("[Wikipedia]\n" + wiki_result.strip())
            sources.append({"name": "Wikipedia", "url": None})
            log.info("Wikipedia returned %d chars.", len(wiki_result))
        else:
            log.warning("Wikipedia returned empty result.")
    except Exception as exc:
        log.warning("Wikipedia failed (may be network issue): %s", type(exc).__name__)

    combined = "\n\n".join(collected)

    return {
        **state,
        "research_results": combined,
        "research_sources": sources,
    }


# ── Node 3: validate_research ─────────────────────────────────────────────────

def validate_research(state: WorkflowState) -> WorkflowState:
    log.info("NODE: validate_research")
    results = state.get("research_results", "")
    sources = state.get("research_sources", [])

    if not results or len(results.strip()) < 50:
        log.error("Research returned insufficient content (len=%d).", len(results))
        return {
            **state,
            "error": (
                "Research step returned no usable content. "
                "Both DuckDuckGo and Wikipedia tools failed or returned empty results. "
                "Cannot proceed to synthesis."
            ),
            "execution_status": "failed",
            "validation_passed": False,
        }

    log.info(
        "Research validation passed. Sources: %s, content length: %d",
        sources, len(results),
    )
    return {
        **state,
        "validation_passed": True,
    }


# ── Node 4: synthesize ────────────────────────────────────────────────────────

_SYNTHESIS_SYSTEM = (
    "You are a research assistant producing a structured report.\n\n"
    "RULES:\n"
    "1. Base your report ONLY on the research evidence provided below.\n"
    "2. Do NOT invent facts, dates, statistics, URLs, or citations.\n"
    "3. Do NOT use your own training knowledge to fill gaps.\n"
    "4. If the evidence does not support a claim, do not make that claim.\n"
    "5. Clearly label which facts come from which source (DuckDuckGo, Wikipedia).\n"
    "6. If evidence is insufficient for a section, explicitly say so.\n"
    "7. Produce a readable, structured report with:\n"
    "   - Title\n"
    "   - Executive Summary (3-5 sentences based strictly on evidence)\n"
    "   - Key Findings (bullet points, each attributed to a source)\n"
    "   - Limitations / Gaps (what the sources did not cover)\n"
    "   - Sources Used\n"
)


def synthesize(state: WorkflowState) -> WorkflowState:
    log.info("NODE: synthesize")
    query = state.get("research_query", "unknown topic")
    results = state.get("research_results", "")

    prompt_content = (
        "Research Topic: " + query + "\n\n"
        "Retrieved Evidence:\n" + results + "\n\n"
        "Produce the structured report now."
    )

    messages = [
        SystemMessage(content=_SYNTHESIS_SYSTEM),
        HumanMessage(content=prompt_content),
    ]

    try:
        log.info("Calling LLM for synthesis...")
        response = llm.invoke(messages)
        report = response.content.strip()
        log.info("Synthesis complete. Report length: %d chars.", len(report))
    except Exception as exc:
        log.error("LLM synthesis failed: %s", exc)
        return {
            **state,
            "error": "LLM synthesis failed: " + type(exc).__name__ + ": " + str(exc),
            "execution_status": "failed",
        }

    return {
        **state,
        "synthesized_report": report,
    }


# ── Node 5: validate_output ───────────────────────────────────────────────────

def validate_output(state: WorkflowState) -> WorkflowState:
    log.info("NODE: validate_output")
    report = state.get("synthesized_report", "")
    filename = state.get("output_filename", "")

    if not report or len(report.strip()) < 100:
        log.error("Synthesized report is too short or empty (len=%d).", len(report))
        return {
            **state,
            "error": "Synthesized report is empty or too short. Refusing to save.",
            "execution_status": "failed",
            "validation_passed": False,
        }

    safe_name = _safe_filename(filename or "research_" + _stamp() + ".txt")
    if safe_name != filename:
        log.info("Filename sanitized: %s -> %s", filename, safe_name)

    log.info("Output validation passed. Filename: %s", safe_name)
    return {
        **state,
        "output_filename": safe_name,
        "validation_passed": True,
    }


# ── Node 6: save_report ───────────────────────────────────────────────────────

def save_report(state: WorkflowState) -> WorkflowState:
    log.info("NODE: save_report")
    report = state.get("synthesized_report", "")
    filename = state.get("output_filename", "research_" + _stamp() + ".txt")

    try:
        result = save_to_txt.invoke({"data": report, "filename": filename})
        log.info("Save result: %s", result)
        return {
            **state,
            "save_status": result,
            "execution_status": "complete",
        }
    except Exception as exc:
        log.error("Save failed: %s", exc)
        return {
            **state,
            "save_status": "Save failed: " + type(exc).__name__ + ": " + str(exc),
            "execution_status": "failed",
            "error": "Save failed: " + str(exc),
        }


# ── Node 7: final_response ────────────────────────────────────────────────────

def final_response(state: WorkflowState) -> WorkflowState:
    log.info("NODE: final_response")
    status = state.get("execution_status", "unknown")
    error = state.get("error")
    query = state.get("research_query", "")
    sources = state.get("research_sources", [])
    filename = state.get("output_filename", "")
    save_status = state.get("save_status", "")
    report = state.get("synthesized_report", "")

    if status == "complete":
        summary = report[:500] + ("..." if len(report) > 500 else "")
        source_names = ", ".join(
            s["name"] if isinstance(s, dict) else str(s) for s in sources
        ) if sources else "None"
        response = (
            "Research workflow completed successfully.\n\n"
            "Topic: " + query + "\n"
            "Sources used: " + source_names + "\n"
            "Report saved to: " + filename + "\n"
            "Save status: " + save_status + "\n\n"
            "Report preview:\n" + summary
        )
    else:
        response = (
            "Research workflow failed.\n\n"
            "Topic: " + query + "\n"
            "Error: " + (error or "Unknown error") + "\n"
            "Status: " + status + "\n"
        )

    log.info("Workflow status: %s", status)
    return {**state, "final_response": response}


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_input(state: WorkflowState) -> str:
    if state.get("execution_status") == "failed":
        return "final_response"
    return "research"


def route_after_research_validation(state: WorkflowState) -> str:
    if state.get("execution_status") == "failed":
        return "final_response"
    return "synthesize"


def route_after_synthesize(state: WorkflowState) -> str:
    if state.get("execution_status") == "failed":
        return "final_response"
    return "validate_output"


def route_after_output_validation(state: WorkflowState) -> str:
    if state.get("execution_status") == "failed":
        return "final_response"
    return "save_report"


def route_after_save(state: WorkflowState) -> str:
    return "final_response"


# ── Graph construction ────────────────────────────────────────────────────────

def build_research_graph(checkpointer: Any = None) -> Any:
    """Build and compile the research workflow StateGraph."""
    graph = StateGraph(WorkflowState)

    # Add nodes
    graph.add_node("validate_input", validate_input)
    graph.add_node("research", research)
    graph.add_node("validate_research", validate_research)
    graph.add_node("synthesize", synthesize)
    graph.add_node("validate_output", validate_output)
    graph.add_node("save_report", save_report)
    graph.add_node("final_response", final_response)

    # Entry edge
    graph.add_edge(START, "validate_input")

    # Conditional edges
    graph.add_conditional_edges("validate_input", route_after_input)
    graph.add_edge("research", "validate_research")
    graph.add_conditional_edges("validate_research", route_after_research_validation)
    graph.add_conditional_edges("synthesize", route_after_synthesize)
    graph.add_conditional_edges("validate_output", route_after_output_validation)
    graph.add_conditional_edges("save_report", route_after_save)

    # Terminal edge
    graph.add_edge("final_response", END)

    return graph.compile(checkpointer=checkpointer)


# ── Public entry point ────────────────────────────────────────────────────────

def run_research_workflow(
    user_request: str,
    thread_id: str = None,
    use_checkpointer: bool = True,
) -> dict:
    """
    Execute the research workflow for a user request.

    Args:
        user_request: Natural-language research request from the user.
        thread_id: Stable conversation ID. A fresh UUID is generated if None.
        use_checkpointer: Whether to attach RedisSaver. Set False for testing.

    Returns:
        The final workflow state dict.
    """
    if not thread_id:
        thread_id = str(uuid.uuid4())

    log.info("=" * 60)
    log.info("RESEARCH WORKFLOW STARTED")
    log.info("Thread ID: %s", thread_id)
    log.info("Request: %s", user_request)
    log.info("=" * 60)

    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "user_request": user_request,
        "execution_status": "running",
    }

    if use_checkpointer:
        with RedisSaver.from_conn_string(REDIS_URI) as checkpointer:
            checkpointer.setup()
            app = build_research_graph(checkpointer=checkpointer)
            final_state = app.invoke(initial_state, config=config)
    else:
        app = build_research_graph(checkpointer=None)
        final_state = app.invoke(initial_state, config=config)

    log.info("=" * 60)
    log.info("WORKFLOW COMPLETE - status: %s", final_state.get("execution_status"))
    log.info("=" * 60)

    return final_state


# ── CLI entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        request = " ".join(sys.argv[1:])
    else:
        request = (
            "Research LangGraph and summarize its core workflow concepts. "
            "Save the findings to a uniquely named text file."
        )

    result = run_research_workflow(request)

    print("\n" + "=" * 60)
    print("FINAL RESPONSE")
    print("=" * 60)
    print(result.get("final_response", "No response generated."))
    print("=" * 60)
