# LLM-based test generation pipeline

## How to Run the Pipeline

### 1. Create virtual environments & install dependencies

Create virtual environment:

```bash
python -m venv .venv
```

Activate virtual environment:

- Windows (Command Prompt)

```cmd
.venv\Scripts\activate
```

- Windows (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
```

- macOS/Linux

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Download libraries and construct Maven projects

Run:

```bash
python libraries_builder/download.py
```

This step reads Maven coordinates from: `csv_data/evosuite_results_small.csv`.

For each row, it:

- Downloads the `-sources.jar` from Maven Central.
- Extracts Java source files into `src/main/java`.
- Downloads the artifact `pom.xml`.
- Adds the required JUnit, Mockito, Surefire, and JaCoCo configuration.
- Compiles the generated Maven project.
- Keeps only libraries that compile successfully.

### 3. Run the LLM test-generation pipeline

This step generates JUnit 4 tests for a selected Maven library, validates them with Maven, repairs failing tests using the LLM, and records JaCoCo coverage.

Run:

```bash
python main.py --library <group_id>:<artifact_id>:<version>
```

Then choose a mode:

1. Run all Java classes in the selected library
2. Run one Java class in the selected library

Available arguments:

```text
--library         Maven coordinates of the target library.
                  Example: org.apache.commons:commons-csv:1.8

--libraries-root  Root folder containing downloaded libraries.
                  Default: libraries_initial

--source          Java file relative to src/main/java.
                  Only needed when running one class.
                  Example: org/apache/commons/csv/CSVParser.java

--model           Ollama model preset to use.
                  Default: qwen_coder_small

--attempts        Maximum number of repair attempts after a generated test fails.
                  Default: 2
```

Example: run all classes in a library:

```
python main.py --library org.apache.commons:commons-csv:1.8
```

Example: run one class:

```
python main.py --library org.apache.commons:commons-csv:1.8 --source org/apache/commons/csv/CSVParser.java
```

Example: use a different model and repair limit:

```
python main.py --library org.apache.commons:commons-csv:1.8 --model qwen_coder_small --attempts 3
```

To see all options:

```
python main.py --help
```

Generated tests are written to:

`<library>/src/test/java/`

Coverage results are appended to:

`csv_data/llm_coverage.csv`

## Run Pipeline with Streamlit UI

```bash
pip install streamlit
streamlit run streamlit_app.py
```

The UI page will then be available at `http://localhost:8501`.
