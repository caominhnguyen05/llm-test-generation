from dataclasses import replace
from pathlib import Path

from pipeline_config import config_from_args, parse_args
from pipeline_runner import run_library_pipeline, run_pipeline


def choose_run_mode() -> str:
    print("Choose run mode:")
    print("1. Run all Java classes in the selected library")
    print("2. Run one Java class in the selected library")
    return input("Enter option (1 or 2): ").strip()


def main() -> None:
    args = parse_args()
    config = config_from_args(args)
    mode = choose_run_mode()

    if mode == "1":
        run_library_pipeline(config)
        return

    if mode == "2":
        if not args.source:
            source = input("Java file relative to src/main/java: ").strip()
            if not source:
                print("No source file provided.")
                return
            config = replace(config, source=Path(source))
        run_pipeline(config)
        return

    print("Invalid option. Please enter 1 or 2.")


if __name__ == "__main__":
    main()
