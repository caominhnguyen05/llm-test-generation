from pipeline_config import parse_args
from pipeline_runner import run_library_pipeline

def main() -> None:
    config = parse_args()
    run_library_pipeline(config)

if __name__ == "__main__":
    main()