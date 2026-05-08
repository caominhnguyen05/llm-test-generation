from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import csv
from pathlib import Path

import streamlit as st

from llm.config import available_model_names
from pipeline_config import DEFAULT_MAX_REPAIR_ATTEMPTS, DEFAULT_OLLAMA_MODEL_NAME


ROOT = Path(__file__).resolve().parent
LIBRARIES_ROOT = ROOT / "libraries_small"
CSV_ROOT = ROOT / "csv_data"


st.set_page_config(
    page_title="LLM Test Pipeline",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #05070d;
            --blue: #0071e3;
            --blue-soft: #e8f2ff;
            --line: rgba(8, 12, 22, 0.10);
            --muted: #657184;
            --panel: rgba(255, 255, 255, 0.82);
        }

        .stApp {
            background:
                linear-gradient(180deg, #f7fbff 0%, #ffffff 34%, #f4f6fa 100%);
            color: var(--ink);
        }

        [data-testid="stSidebar"] {
            background: #05070d;
        }

        [data-testid="stSidebar"] * {
            color: #f5f7fb;
        }

        [data-testid="stSidebar"] [data-baseweb="select"] * {
            color: var(--ink);
        }

        .hero {
            padding: 34px 0 18px;
            border-bottom: 1px solid var(--line);
            margin-bottom: 20px;
        }

        .hero h1 {
            font-size: 46px;
            line-height: 1.02;
            letter-spacing: 0;
            margin: 0 0 8px;
            color: var(--ink);
            font-weight: 760;
        }

        .hero p {
            max-width: 780px;
            color: var(--muted);
            font-size: 17px;
            margin: 0;
        }

        .metric-card {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 16px 18px;
            background: var(--panel);
            min-height: 88px;
        }

        .metric-card span {
            color: var(--muted);
            font-size: 12px;
            text-transform: uppercase;
        }

        .metric-card strong {
            display: block;
            margin-top: 8px;
            font-size: 24px;
            color: var(--ink);
        }

        .stage {
            border-left: 3px solid var(--blue);
            padding: 10px 0 10px 14px;
            margin: 8px 0 16px;
        }

        .stage h3 {
            margin: 0;
            color: var(--ink);
            font-size: 18px;
        }

        .stage p {
            margin: 4px 0 0;
            color: var(--muted);
        }

        .stButton > button {
            border-radius: 999px;
            background: #0071e3;
            color: #ffffff;
            border: 1px solid #0071e3;
            font-weight: 650;
            min-height: 42px;
        }

        .stButton > button:hover {
            background: #005ec4;
            border-color: #005ec4;
            color: #ffffff;
        }

        [data-testid="stCodeBlock"] {
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.10);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def library_names() -> list[str]:
    if not LIBRARIES_ROOT.exists():
        return []
    return sorted(path.name for path in LIBRARIES_ROOT.iterdir() if path.is_dir())


def source_files(library: str) -> list[str]:
    source_root = LIBRARIES_ROOT / library / "src/main/java"
    if not source_root.exists():
        return []
    return [str(path.relative_to(source_root)).replace("\\", "/") for path in sorted(source_root.rglob("*.java"))]


def csv_outputs() -> list[str]:
    if not CSV_ROOT.exists():
        return []
    return sorted(path.name for path in CSV_ROOT.glob("*.csv"))


def stream_command(command: list[str], title: str, timeout: int | None = None) -> int:
    st.markdown(f'<div class="stage"><h3>{title}</h3><p>Live process output</p></div>', unsafe_allow_html=True)
    status = st.status("Running", expanded=True)
    output_box = st.empty()
    progress = st.progress(0)
    lines: list[str] = []
    line_queue: queue.Queue[str | None] = queue.Queue()

    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    def read_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            line_queue.put(line.rstrip())
        line_queue.put(None)

    threading.Thread(target=read_output, daemon=True).start()

    start = time.time()
    tick = 0
    finished_output = False
    while process.poll() is None or not finished_output:
        try:
            item = line_queue.get(timeout=0.1)
            if item is None:
                finished_output = True
            else:
                lines.append(item)
        except queue.Empty:
            pass

        tick = (tick + 1) % 100
        progress.progress(tick)
        output_box.code("\n".join(lines[-260:]) or "Waiting for output...", language="text")

        if timeout and time.time() - start > timeout:
            process.kill()
            lines.append(f"Timed out after {timeout} seconds.")
            break

    return_code = process.wait()
    progress.progress(100)
    output_box.code("\n".join(lines[-320:]) or "No output.", language="text")

    if return_code == 0:
        status.update(label="Completed", state="complete", expanded=False)
    else:
        status.update(label=f"Failed with exit code {return_code}", state="error", expanded=True)
    return return_code


def render_header() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>LLM Test Pipeline</h1>
            <p>Generate, validate, repair, and measure Java unit tests from one focused console.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(libraries: list[str]) -> None:
    cols = st.columns(3)
    test_count = len(list(LIBRARIES_ROOT.rglob("*Test.java"))) if LIBRARIES_ROOT.exists() else 0
    report_count = len(list(LIBRARIES_ROOT.rglob("target/site/jacoco/jacoco.xml"))) if LIBRARIES_ROOT.exists() else 0
    metrics = [
        ("Libraries", str(len(libraries))),
        ("Generated Tests", str(test_count)),
        ("Coverage Reports", str(report_count)),
    ]
    for col, (label, value) in zip(cols, metrics):
        col.markdown(f'<div class="metric-card"><span>{label}</span><strong>{value}</strong></div>', unsafe_allow_html=True)


def pipeline_tab(libraries: list[str]) -> None:
    st.subheader("Pipeline")
    if not libraries:
        st.error("No libraries found in libraries_small.")
        return

    col_a, col_b, col_c = st.columns([1.25, 1.25, 0.8])
    library = col_a.selectbox("Library", libraries)
    mode = col_b.segmented_control("Mode", ["Single class", "Whole library"], default="Single class")
    model = col_c.selectbox("Model", available_model_names(), index=available_model_names().index(DEFAULT_OLLAMA_MODEL_NAME))
    attempts = st.slider("Repair attempts", 0, 5, DEFAULT_MAX_REPAIR_ATTEMPTS)

    sources = source_files(library)
    selected_source = None
    if mode == "Single class":
        if not sources:
            st.warning("This library has no Java source files.")
            return
        selected_source = st.selectbox("Source file", sources)

    command = [sys.executable, "-u", "-c"]
    if mode == "Whole library":
        code = (
            "from pipeline_config import PipelineConfig; "
            "from pipeline_runner import run_library_pipeline; "
            f"run_library_pipeline(PipelineConfig(library={library!r}, source=__import__('pathlib').Path(''), "
            f"model=__import__('llm.config').config.get_model({model!r}), attempts={attempts}))"
        )
    else:
        code = (
            "from pathlib import Path; "
            "from pipeline_config import PipelineConfig; "
            "from pipeline_runner import run_pipeline; "
            "from llm.config import get_model; "
            f"run_pipeline(PipelineConfig(library={library!r}, source=Path({selected_source!r}), "
            f"model=get_model({model!r}), attempts={attempts}))"
        )
    command.append(code)

    if st.button("Run Pipeline", use_container_width=True):
        stream_command(command, "Generate and Validate Tests")


def coverage_tab(libraries: list[str]) -> None:
    st.subheader("Coverage")
    scope = st.segmented_control("Scope", ["All libraries", "One library"], default="All libraries")
    output_name = st.text_input("CSV output", value="csv_data/coverage_results.csv")

    root_arg = "libraries_small"
    if scope == "One library" and libraries:
        library = st.selectbox("Library", libraries, key="coverage_library")
        root_arg = str(Path("libraries_small") / library)

    command = [sys.executable, "-u", "coverage/run_coverage.py", root_arg, "--output", output_name]
    if st.button("Run Coverage", use_container_width=True):
        stream_command(command, "Run JaCoCo Coverage")
        output_path = ROOT / output_name
        if output_path.exists():
            with open(output_path, newline="", encoding="utf-8") as file:
                st.dataframe(list(csv.DictReader(file)), use_container_width=True)


def builder_tab() -> None:
    st.subheader("Library Builder")
    st.write("Input CSV files")
    selected_csv = None
    csvs = csv_outputs()
    if csvs:
        selected_csv = st.selectbox("Dataset", csvs)
    else:
        st.warning("No CSV files found in csv_data.")

    st.caption("The builder uses libraries_builder/download.py and keeps only libraries that compile.")
    if st.button("Download and Compile Libraries", use_container_width=True, disabled=not selected_csv):
        stream_command([sys.executable, "-u", "libraries_builder/download.py"], "Download, Build, and Compile")


def main() -> None:
    apply_theme()
    render_header()
    libraries = library_names()
    render_metrics(libraries)
    st.divider()

    pipeline, coverage, builder = st.tabs(["Pipeline", "Coverage", "Libraries"])
    with pipeline:
        pipeline_tab(libraries)
    with coverage:
        coverage_tab(libraries)
    with builder:
        builder_tab()


if __name__ == "__main__":
    main()
