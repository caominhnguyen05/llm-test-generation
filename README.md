# LLM-based Test Generation Pipeline

This repository contains the implementation and experimental framework used in the Bachelor's thesis project to evaluate LLM-based unit test generation for Java libraries. The pipeline generates JUnit 4 test suites, validates and repairs generated tests, and records code coverage, test validity, runtime, and cost metrics.

## Prerequisites

- Python 3.10+
- Java (JDK 8 or later)
- Maven
- Ollama (for local model experiments)
- OpenRouter credits and API key (for cloud-hosted model experiment)

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
python src/main.py --mode final --attempts 2
```

### SQ3: Effect of Iterative Repair

Run the pipeline four times with different maximum numbers of repair attempts:

```bash
python src/main.py --mode repair --attempts 0
```

```bash
python src/main.py --mode repair --attempts 1
```

```bash
python src/main.py --mode repair --attempts 2
```

```bash
python src/main.py --mode repair --attempts 3
```

### SQ4: Local Model vs. Cloud-Hosted Model Comparison

The local-model results used in this comparison are the same results generated in SQ1 and SQ2. If you already ran the SQ1/SQ2 experiment, no additional Ollama run is required.

To obtain the cloud-hosted model results via OpenRouter, run:

```bash
python src/main.py --mode final --attempts 2 --llm_backend openrouter
```

Note that you need an OpenRouter API Key set in `.env` file to run the SQ4 experiment with OpenRouter.

### Arguments

```text
--mode          Required. Either repair or final.
                repair reads datasets/sample_20_libraries.csv.
                final reads datasets/sample_34_libraries.csv.

--attempts      Required. Maximum number of repair attempts per generated test.
                Use 0 to run generation without repair.

--library       Optional. Maven coordinate groupId:artifactId:version.
                If not provided, all libraries from the input CSV are processed.

--llm_backend   Optional. ollama or openrouter. Default is ollama.
```

## Incremental Execution

The pipeline automatically skips libraries that already have both coverage and cost results recorded in the corresponding CSV files `results`/ folder. This allows interrupted experiments to be resumed safely.

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

The experiment pipeline produces three types of outputs: result CSVs, generated JUnit test suites, and execution logs.

### Results

Summary metrics and evaluation results (CSV files) are written to:

```text
results/
├── final/
│   ├── cloud_llm/
│   │   ├── coverage.csv
│   │   ├── cost.csv
│   │   └── compile_failures.csv
│   └── local_llm/
│       ├── coverage.csv
│       ├── cost.csv
│       └── compile_failures.csv
└── repair/
    └── repair_<attempts>/
        ├── coverage.csv
        ├── cost.csv
        └── compile_failures.csv
```

- `final/cloud_llm/` contains results for the cloud-hosted model accessed through OpenRouter.
- `final/local_llm/` contains results for the locally hosted model accessed through Ollama.
- `repair/repair_<attempts>/` contains results for iterative repair experiments with the specified repair budget.

The repository distinguishes between:

- `paper_results/`: final experimental results reported in the thesis
- `results/`: output directory used for reruns

Rerunning the pipeline will write new outputs to `results/` and will not modify `paper_results/`.

### Generated Test Suites

Generated JUnit test suites in Maven test projects are stored under:

```text
generated_tests/
├── tests_final_<llm_backend>/
└── tests_repair_<attempts>/
```

### Logs and Intermediate Artifacts

Execution logs, generation/repair prompts, and raw LLM responses are written to:

```text
experiment_logs/
```

These files are useful for inspecting individual experiment runs and diagnosing failures.

## Repository Layout

```text
llm-test/
├── requirements.txt            # Python dependencies
├── README.md
│
├── src/
|   |── main.py                 # CLI entry point
│   ├── pipeline/               # Preprocessing, test generation, validation, postprocessing, metrics
│   ├── library_prep/           # Maven library download and test project setup
│   ├── coverage/               # Parse Surefire reports, ignore failing tests, JaCoCo coverage
|   |── figures/                # Scripts for generating figures and tables
│   ├── llm/                    # Ollama/OpenRouter clients and prompt handling
│   └── tools/
│       └── java-api-extractor/ # Java helper for extracting public API summaries
│
├── datasets/                   # Sample library lists and EvoSuite baseline result
│
├── paper_results/              # Final experimental results used in the thesis*
│
├── generated_tests/            # Tests generated by the LLMs (not tracked by Git)
│
└── experiment_logs/            # Raw LLM responses, Maven errors, prompts (not tracked by Git)
```

> Note: `generated_tests/` and `experiment_logs/` are excluded from version control due to size but are fully reproducible by running the experiment pipeline.
