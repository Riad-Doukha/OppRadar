# Every notebook must run top-to-bottom headless, offline and without a single
# remote call: that is what makes the RUN_LIVE_LLM cost gate trustworthy. Each
# notebook is executed in a real Jupyter kernel started with THIS interpreter,
# `LLM_PROVIDER=fake`, dummy keys (so ai/.env can never leak one in) and no
# RUN_LIVE_LLM, then its captured output is checked for the offline markers.

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

if sys.platform == "win32":
    # zmq/tornado cannot use the Proactor loop on Windows (warning + hung kernels).
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "notebooks"
NOTEBOOKS = sorted(p.name for p in NOTEBOOK_DIR.glob("*.ipynb"))

# What the offline run has to show per notebook (beyond "no cell raised").
OFFLINE_MARKERS = {
    "00_setup.ipynb": (
        "live LLM: no",
        "skipped (offline): set RUN_LIVE_LLM=1 to spend a real Gemini call here",
        "skipped (offline): set RUN_LIVE_LLM=1 to run a live Tavily search here",
    ),
    "01_document_intake.ipynb": ("method=pdf_text",),
    "02_profile_builder.ipynb": ("provider: fake",),
    "03_discovery.ipynb": (
        "live Tavily/RSS: no",
        "OFFLINE: loaded data/samples/tavily_response_sample.json (no network)",
    ),
    "04_page_extraction.ipynb": (
        "LLM usage for this step:",
        "skipped (OFFLINE mode): set RUN_LIVE_LLM=1",
    ),
    "05_matching.ipynb": (
        "live LLM: no",
        "phrasing skipped (offline)",
        "score_user: 5 profiles x 32 opportunities",
    ),
}

# Kernel environment: offline provider, dummy keys, no gate, no downloads.
OFFLINE_ENV = {
    "LLM_PROVIDER": "fake",
    # The notebook kernel deliberately uses the REAL local embedding model (from
    # the HuggingFace cache, with downloads forbidden): 05_matching must prove
    # score_user works end-to-end with real vectors, not only with the fake one.
    "EMBEDDING_PROVIDER": "sentence_transformers",
    # ai/.env may hold RUN_LIVE_LLM=1 for a live session: an empty var does NOT
    # override dotenv, so the gate has to be switched OFF explicitly.
    "RUN_LIVE_LLM": "0",
    "GEMINI_API_KEY": "offline-test-key-not-a-secret",
    "TAVILY_API_KEY": "offline-test-key-not-a-secret",
    "LLM_MIN_DELAY_SECONDS": "0",  # 1s of politeness per fake call only slows the suite
    "HF_HUB_OFFLINE": "1",  # never download a model during a test run
    "TRANSFORMERS_OFFLINE": "1",
}


def _kernel_spec(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:
    """Write a kernelspec that starts the notebooks with `sys.executable`."""
    root = tmp_path_factory.mktemp("jupyter")
    spec_dir = root / "kernels" / "oppradar-test"
    spec_dir.mkdir(parents=True)
    (spec_dir / "kernel.json").write_text(
        json.dumps(
            {
                "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                "display_name": "OppRadar pytest kernel",
                "language": "python",
            }
        ),
        encoding="utf-8",
    )
    return "oppradar-test", str(root)


def _captured_text(nb) -> str:
    """Everything the notebook printed (streams, errors, displayed tables)."""
    parts: list[str] = []
    for cell in nb.cells:
        for out in cell.get("outputs", []):
            parts.append(str(out.get("text", "")))
            parts.append(str(out.get("evalue", "")))
            plain = out.get("data", {}).get("text/plain", "")
            parts.append(plain if isinstance(plain, str) else "".join(plain))
    return "\n".join(parts)


def _run_offline(name: str, kernel: tuple[str, str]) -> str:
    """Execute one notebook headless with the offline environment."""
    kernel_name, jupyter_path = kernel
    nb = nbformat.read(NOTEBOOK_DIR / name, as_version=4)
    client = NotebookClient(
        nb,
        timeout=600,  # a cold OCR / embedding load may take a while
        kernel_name=kernel_name,
        resources={"metadata": {"path": str(NOTEBOOK_DIR)}},
    )
    with pytest.MonkeyPatch.context() as mp:
        for key, value in OFFLINE_ENV.items():
            mp.setenv(key, value)
        # conftest.py points the pytest process at a throwaway DATA_DIR; the
        # notebooks must read the committed samples from ai/data instead.
        mp.delenv("DATA_DIR", raising=False)
        mp.setenv("JUPYTER_PATH", jupyter_path)
        client.execute()
    return _captured_text(nb)


@pytest.fixture(scope="module")
def notebook_outputs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Run every notebook once, offline, and keep what they printed."""
    kernel = _kernel_spec(tmp_path_factory)
    return {name: _run_offline(name, kernel) for name in NOTEBOOKS}


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_runs_offline_without_live_calls(name, notebook_outputs):
    text = notebook_outputs[name]

    assert "generativelanguage.googleapis.com" not in text, f"{name} called Gemini offline"
    assert "api.tavily.com" not in text, f"{name} searched Tavily offline"
    for marker in OFFLINE_MARKERS[name]:
        assert marker in text, f"{name}: expected {marker!r} in the offline output"


def test_run_live_llm_gate_stays_closed(notebook_outputs):
    """RUN_LIVE_LLM unset -> notebook 04 runs every step on the fake provider."""
    text = notebook_outputs["04_page_extraction.ipynb"]

    assert "live LLM: no" in text
    assert "provider: fake" in text
    assert "Step 6 mode: OFFLINE fake provider (no live call)" in text
    assert "OFFLINE mode (fake provider): grading" in text
