# LLM-based Test Generation Pipeline

This repository contains the implementation and experimental framework used in the Bachelor's thesis project to evaluate LLM-based unit test generation for Java libraries. The pipeline generates JUnit 4 test suites, validates and repairs generated tests, and records code coverage, test validity, runtime, and cost metrics.

## Prerequisites

- Python 3.10+
- Java (JDK 8 or later)
- Maven
- Ollama (for local model experiments)

Create and activate a Python virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## LLM Backends

- `--llm_backend ollama` uses the local Ollama model configured in `llm/config.py`.
- `--llm_backend openrouter` requires `OPENROUTER_API_KEY` environment variable to be set in `.env`.

## Reproducing Experimental Results

The following commands reproduce the experiments for each sub-question.

### SQ1 & SQ2: Coverage & Test Validity Evaluation

Run the pipeline using the local model via Ollama with 2 repair attempts:

```bash
python main.py --mode final --attempts 2
```

### SQ3: Effect of Iterative Repair

Run the pipeline four times with different maximum numbers of repair attempts:

```bash
python main.py --mode repair --attempts 0
```

```bash
python main.py --mode repair --attempts 1
```

```bash
python main.py --mode repair --attempts 2
```

```bash
python main.py --mode repair --attempts 3
```

### SQ4: Local Model vs. Cloud-Hosted Model Comparison

The local-model results used in this comparison are the same results generated for SQ1 and SQ2. If you have already run the SQ1/SQ2 experiment, no additional Ollama run is required.

To obtain the cloud-hosted model results via OpenRouter, run:

```bash
python main.py --mode final --attempts 2 --llm_backend openrouter
```

Note that you need an OpenRouter API Key set in `.env` file to run the SQ4 experiment with OpenRouter.

### Arguments

```text
--mode          Required. Either repair or final.
                repair reads csv_data/libraries_repair.csv.
                final reads csv_data/libraries_final.csv.

--attempts      Required. Maximum number of repair attempts per generated test.
                Use 0 to run generation without repair.

--library       Optional. Maven coordinate groupId:artifactId:version.
                If omitted, all libraries from the mode CSV are processed.

--llm_backend   Optional. ollama or openrouter. Default: ollama.
```

## Incremental Execution

The pipeline automatically skips libraries that already have both coverage and cost results recorded. This allows interrupted experiments to be resumed safely.

## What the Pipeline Does

For each library, the pipeline:

1. Downloads the binary jar and sources jar from Maven Central.
2. Extracts sources into `prompt_sources/`.
3. Creates a minimal Maven project with JUnit, Mockito, Surefire, and JaCoCo.
4. Finds testable Java source files.
5. Extracts a class API summary with `tools/java-api-extractor`.
6. Generates a JUnit test with the configured LLM backend.
7. Validates structure, compilation, and runtime behavior.
8. Repairs failing tests up to `--attempts`.
9. Runs coverage after ignoring failing/erroring test methods.
10. Writes result CSV files.

If a library has a pipeline error such as API extraction failure, coverage and runtime/cost rows are not written for that library. If the pipeline completes but no generated test class compiles, a zero coverage row is written.

## Outputs

Results are written to:

```text
results/final/<llm_backend>/
results/repair/repair_<attempts>/
```

Generated tests and prepared Maven projects are stored under:

```text
libraries_final_<llm_backend>/
libraries_repair_<attempts>/
```

Execution logs, prompts, LLM responses, and repair traces are written to:

```text
experiment_logs/
```

## Repository Layout

```text
main.py                     CLI entry point
pipeline/                   Orchestration, prompting, validation, metrics
library_prep/               Maven library download and project setup
coverage/                   Surefire parsing, failing-test ignoring, JaCoCo rows
llm/                        Ollama/OpenRouter client and prompts
tools/java-api-extractor/   Java helper used to summarize public class APIs
csv_data/                   Input library lists and baseline data
results/                    Experiment CSV outputs and analysis/plotting scripts
experiment_logs/            Saved prompts, LLM responses, and repair errors
```
