"""Command-line interface for VParse File to Markdown service."""

import sys
import argparse

from . import config
from . import server


def main():
    """Entry point for the command-line interface."""
    parser = argparse.ArgumentParser(description="VParse File to Markdown conversion service")

    parser.add_argument(
        "--output-dir", "-o", type=str, help="Directory to save converted files (default: ./downloads)"
    )

    parser.add_argument(
        "--transport",
        "-t",
        type=str,
        default="stdio",
        help="Transport protocol (default: stdio, options: sse, streamable-http)",
    )

    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8001,
        help="Server port (default: 8001, effective only with HTTP protocol)",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Server host address (default: 127.0.0.1, effective only with HTTP protocol)",
    )

    args = parser.parse_args()

    # Validate argument consistency
    if args.transport == "stdio" and (args.host != "127.0.0.1" or args.port != 8001):
        print("Warning: --host and --port parameters are ignored in STDIO mode", file=sys.stderr)

    # Validate API key - moved here so --help etc. can run without key
    if not config.VPARSE_API_KEY:
        print(
            "Error: VPARSE_API_KEY environment variable is required to start the service."
            "\nPlease check if the environment variable is set, for example:"
            "\n  export VPARSE_API_KEY='your_actual_api_key'"
            "\nAlternatively, ensure the variable is defined in a .env file at the project root."
            "\n\nYou can use --help to view available command-line options.",
            file=sys.stderr,  # Output error message to stderr
        )
        sys.exit(1)

    # Set output directory if provided
    if args.output_dir:
        server.set_output_dir(args.output_dir)

    # Print configuration information
    print("VParse File to Markdown conversion service starting...")
    if args.transport in ["sse", "streamable-http"]:
        print(f"Server address: {args.host}:{args.port}")
    print("Press Ctrl+C to exit the service")

    server.run_server(mode=args.transport, port=args.port, host=args.host)


if __name__ == "__main__":
    main()
