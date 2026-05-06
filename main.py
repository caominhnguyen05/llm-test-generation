from pipeline_config import config_from_args, parse_args
from pipeline_runner import run_pipeline


def main() -> None:
    run_pipeline(config_from_args(parse_args()))


if __name__ == "__main__":
    main()
