JACOCO_VERSION = "0.8.12"

FIELDNAMES = [
    "group_id",
    "artifact_id",
    "version",
    "source",
    "instruction_coverage",
    "branch_coverage",
    "line_coverage",
    "complexity_coverage",
    "method_coverage",
    "class_coverage",
    "tests_passed",
    "tests_total",
    "percentage_passed",
    "jacoco_success",
]

COUNTER_FIELDS = {
    "INSTRUCTION": "instruction_coverage",
    "BRANCH": "branch_coverage",
    "LINE": "line_coverage",
    "COMPLEXITY": "complexity_coverage",
    "METHOD": "method_coverage",
    "CLASS": "class_coverage",
}