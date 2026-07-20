def main() -> None:
    # Delegate to the CLI entrypoint
    from .cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
