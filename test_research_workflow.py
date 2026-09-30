"""
test_research_workflow.py
Tests 1-8 for the research workflow.
Run: python test_research_workflow.py
"""
import sys
import uuid
import os
from pathlib import Path

BASE_DIR = Path(r"D:\AI Agent")
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

PASS = "PASS"
FAIL = "FAIL"
NOT_RUN = "NOT RUN"

results = []

def record(test_name, status, detail=""):
    results.append((test_name, status, detail))
    print(f"[{status}] {test_name}" + (f" — {detail}" if detail else ""))


# ── TEST 1: Graph construction ────────────────────────────────────────────────
print("\n--- TEST 1: Graph construction ---")
try:
    from research_workflow import build_research_graph
    app = build_research_graph(checkpointer=None)
    assert app is not None
    record("Graph construction", PASS, "Compiled without checkpointer")
except Exception as e:
    record("Graph construction", FAIL, str(e))
    print("FATAL: Cannot continue without graph. Exiting.")
    sys.exit(1)


# ── TEST 2: State propagation (no LLM) ───────────────────────────────────────
print("\n--- TEST 2: State propagation ---")
try:
    from research_workflow import (
        validate_input, validate_research, WorkflowState
    )

    # validate_input
    s0: WorkflowState = {"user_request": "LangGraph workflow concepts", "execution_status": "running"}
    s1 = validate_input(s0)
    assert s1.get("research_query"), "research_query missing"
    assert s1.get("output_filename", "").endswith(".txt"), "output_filename missing .txt"
    assert s1.get("execution_status") == "running"

    # validate_research with good data
    s2 = {**s1, "research_results": "A" * 200, "research_sources": ["DuckDuckGo"]}
    s3 = validate_research(s2)
    assert s3.get("validation_passed") is True

    record("State propagation", PASS, f"query={s1['research_query'][:40]}")
except Exception as e:
    record("State propagation", FAIL, str(e))


# ── TEST 3: Research failure handling ─────────────────────────────────────────
print("\n--- TEST 3: Research failure handling ---")
try:
    from research_workflow import validate_research, WorkflowState

    bad_state: WorkflowState = {
        "user_request": "test",
        "research_query": "test",
        "research_results": "",
        "research_sources": [],
        "execution_status": "running",
    }
    result_state = validate_research(bad_state)
    assert result_state.get("execution_status") == "failed"
    assert result_state.get("error") is not None
    assert not result_state.get("synthesized_report")

    record("Research failure handling", PASS, "Empty results correctly rejected")
except Exception as e:
    record("Research failure handling", FAIL, str(e))


# ── TEST 4: Synthesis with real LLM ──────────────────────────────────────────
print("\n--- TEST 4: Synthesis (live LLM) ---")
try:
    from research_workflow import synthesize, WorkflowState

    synth_state: WorkflowState = {
        "user_request": "test",
        "research_query": "LangGraph",
        "research_results": (
            "[DuckDuckGo]\nLangGraph is a library for building stateful, multi-step "
            "applications using language models. It provides a StateGraph API with nodes "
            "and edges. It integrates with LangChain.\n\n"
            "[Wikipedia]\nLangGraph extends LangChain to support cyclical computation "
            "and multi-agent workflows. Nodes represent computation steps and edges "
            "define transitions."
        ),
        "research_sources": ["DuckDuckGo", "Wikipedia"],
        "execution_status": "running",
    }
    out = synthesize(synth_state)

    if out.get("execution_status") == "failed":
        record("Synthesis (live LLM)", FAIL, out.get("error", "unknown"))
    else:
        report = out.get("synthesized_report", "")
        assert len(report) > 100, "Report too short"
        assert "LangGraph" in report or "langgraph" in report.lower()
        record("Synthesis (live LLM)", PASS, f"Report length={len(report)}")
        print("  Report preview:", report[:300].encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
except Exception as e:
    record("Synthesis (live LLM)", FAIL, str(e))


# ── TEST 5: Save with unique filename ─────────────────────────────────────────
print("\n--- TEST 5: Save (unique test filename) ---")
try:
    from research_workflow import save_report, validate_output, WorkflowState
    import time

    test_fname = f"test_workflow_{uuid.uuid4().hex[:8]}.txt"
    test_report = "A" * 200 + "\nTest research report for workflow validation."

    # validate_output
    vo_state: WorkflowState = {
        "synthesized_report": test_report,
        "output_filename": test_fname,
        "execution_status": "running",
    }
    vo_out = validate_output(vo_state)
    assert vo_out.get("validation_passed") is True

    # save_report
    sr_out = save_report(vo_out)
    assert sr_out.get("execution_status") == "complete", f"status={sr_out.get('execution_status')}"
    assert "successfully" in (sr_out.get("save_status") or "").lower()

    # Confirm file exists
    saved_path = BASE_DIR / "reports" / test_fname
    assert saved_path.exists(), f"File not found: {saved_path}"
    file_content = saved_path.read_text(encoding="utf-8")
    assert "Test research report" in file_content

    record("Save (unique filename)", PASS, f"file={test_fname}, size={saved_path.stat().st_size}B")

    # Clean up test artifact
    saved_path.unlink()
    print("  Test file cleaned up:", test_fname)
except Exception as e:
    record("Save (unique filename)", FAIL, str(e))


# ── TEST 6: End-to-end workflow ───────────────────────────────────────────────
print("\n--- TEST 6: End-to-end workflow (no checkpointer) ---")
try:
    from research_workflow import run_research_workflow

    request = (
        "Research LangGraph and summarize its core workflow concepts. "
        "Save the findings to a uniquely named text file."
    )
    tid = "test-e2e-" + uuid.uuid4().hex[:8]

    final = run_research_workflow(
        user_request=request,
        thread_id=tid,
        use_checkpointer=False,
    )

    status = final.get("execution_status")
    sources = final.get("research_sources", [])
    filename = final.get("output_filename", "")
    save_status = final.get("save_status", "")
    response = final.get("final_response", "")

    print("  Status:", status)
    print("  Sources:", sources)
    print("  Filename:", filename)
    print("  Save status:", save_status)
    print("  Response preview:", response[:300].encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))

    if status == "complete":
        # Verify file was written
        fpath = BASE_DIR / "reports" / filename
        exists = fpath.exists()
        record("End-to-end workflow", PASS if exists else FAIL,
               f"status={status}, file_exists={exists}, sources={sources}")
        if exists:
            print(f"  File written: {fpath} ({fpath.stat().st_size}B)")
            # Do NOT delete — leave as evidence
    else:
        error = final.get("error", "")
        record("End-to-end workflow", FAIL, f"status={status}, error={error[:100]}")

except Exception as e:
    record("End-to-end workflow", FAIL, str(e)[:200])


# ── TEST 7: Checkpointing (thread_id used correctly) ─────────────────────────
print("\n--- TEST 7: Checkpointing ---")
try:
    from research_workflow import build_research_graph, validate_input, WorkflowState
    from langgraph.checkpoint.redis import RedisSaver

    tid = "test-checkpoint-" + uuid.uuid4().hex[:8]
    config = {"configurable": {"thread_id": tid}}

    with RedisSaver.from_conn_string("redis://localhost:6379") as checkpointer:
        checkpointer.setup()
        app = build_research_graph(checkpointer=checkpointer)

        # Run a minimal state
        mini_state = {"user_request": "LangGraph", "execution_status": "running"}
        final = app.invoke(mini_state, config=config)

        # Retrieve checkpoint state
        saved = app.get_state(config)
        assert saved is not None
        assert saved.values is not None

        record("Checkpointing", PASS,
               f"thread_id={tid}, status={final.get('execution_status')}")
except Exception as e:
    record("Checkpointing", FAIL, str(e)[:200])


# ── TEST 8: Single-query route regression ─────────────────────────────────────
print("\n--- TEST 8: Regression (existing router) ---")
try:
    from router import route_query
    from tools import search_tool, wiki_tool, save_to_txt
    from langchain_core.tools import BaseTool

    cases = [
        ("What is my preferred backend language?", "memory"),
        ("According to my knowledge base, explain Redis persistence.", "rag"),
        ("Explain what an AI agent is.", "general"),
        ("Search the web for the latest developments in AI agents.", "research"),
        ("Save the findings to a text file.", "file"),
    ]
    all_ok = True
    for q, expected in cases:
        actual = route_query(q)
        ok = actual == expected
        if not ok:
            all_ok = False
        print(f"  {'OK' if ok else 'FAIL'}  expected={expected}  actual={actual}")

    # Also verify tool instances unchanged
    for t in [search_tool, wiki_tool, save_to_txt]:
        assert isinstance(t, BaseTool), f"{t} is not a BaseTool instance"

    record("Regression (existing router)", PASS if all_ok else FAIL)
except Exception as e:
    record("Regression (existing router)", FAIL, str(e))


# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST RESULTS SUMMARY")
print("=" * 60)
for name, status, detail in results:
    print(f"  [{status:8}] {name}" + (f"\n             {detail}" if detail else ""))
print("=" * 60)
passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)
not_run = sum(1 for _, s, _ in results if s == NOT_RUN)
print(f"  PASSED: {passed}  FAILED: {failed}  NOT RUN: {not_run}")
print("=" * 60)
