# LLM Test Generation Pipeline

This repository runs an LLM-based pipeline that generates JUnit 4 tests for Maven library classes, validates and repairs those tests, then records JaCoCo coverage and runtime/cost metrics.

## Setup

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

Install Python dependencies:

```bash
pip install -r requirements.txt
```

You also need Java and Maven available on your path. The pipeline currently calls `mvn.cmd`, so on non-Windows systems the Maven command may need to be adjusted.

For LLM calls:

- `--llm_backend ollama` uses the local Ollama model configured in `llm/config.py`.
- `--llm_backend openrouter` requires `OPENROUTER_API_KEY` in your environment or `.env`.

## Running Experiments

- Run the pipeline for all sample libraries listed in the CSV (with repair mode):

```bash
python main.py --mode repair --attempts <num_attempts>
```

Replace `<num_attempts>` with the maximum number of repair attempts to allow for each generated test class.

- Run final experiment on all sample libraries with Ollama:

```bash
python main.py --mode final --attempts 2 --llm_backend ollama
```

- Run final experiment on all sample libraries with OpenRouter:

```bash
python main.py --mode final --attempts 2 --llm_backend openrouter
```

Run one library (for testing/debugging):

```bash
python main.py --mode repair --attempts <max_attempts> --library <group_id>:<artifact_id>:<version>
```

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

If both coverage and cost rows already exist for a library, `main.py` skips that library.

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

Prepared libraries and generated tests are written under:

```text
libraries_repair_<attempts>/<group_id>/<artifact_id>/<version>/
libraries_final_<llm_backend>/<group_id>/<artifact_id>/<version>/
```

Generated tests are saved in each prepared Maven project:

```text
<library_path>/src/test/java/
```

Experiment logs are written under:

```text
experiment_logs/repair_<attempts>/<group_id>_<artifact_id>_<version>/
experiment_logs/final_<llm_backend>/<group_id>_<artifact_id>_<version>/
```

Result CSV files are written to:

```text
results/repair/repair_<attempts>/coverage.csv
results/repair/repair_<attempts>/cost.csv
results/repair/repair_<attempts>/compile_failures.csv
results/repair/repair_<attempts>/compile_failures_summary.csv

results/final/<llm_backend>/coverage.csv
results/final/<llm_backend>/cost.csv
results/final/<llm_backend>/compile_failures.csv
results/final/<llm_backend>/compile_failures_summary.csv
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
results/                    Experiment CSV outputs and analysis scripts
experiment_logs/            Saved prompts, LLM responses, and repair errors
```
