from dataclasses import dataclass


@dataclass(frozen=True)
class TestCounts:
    total: int = 0
    passed: int = 0
    failed_assertions: int = 0
    runtime_errors: int = 0


@dataclass(frozen=True)
class CoveragePrepResult:
    test_counts: TestCounts
    ignored_methods: int = 0
