from pipeline_config import config_from_args, parse_args
from pipeline_runner import run_library_pipeline

def main() -> None:
    args = parse_args()
    config = config_from_args(args)
    run_library_pipeline(config)

if __name__ == "__main__":
    main()