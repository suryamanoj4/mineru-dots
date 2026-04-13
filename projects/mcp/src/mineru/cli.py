"""Command-line entry point for the MinerU MCP service."""

import sys
import argparse

from . import config
from . import server


def main():
    """Run the MinerU MCP service."""
    parser = argparse.ArgumentParser(description="MinerU file-to-Markdown service")

    parser.add_argument(
        "--output-dir", "-o", type=str, help="Directory for converted files (default: ./downloads)"
    )

    parser.add_argument(
        "--transport",
        "-t",
        type=str,
        default="stdio",
        help="Transport mode (default: stdio; options: sse, streamable-http)",
    )

    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8001,
        help="Server port (default: 8001, used only for HTTP transports)",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1, used only for HTTP transports)",
    )

    args = parser.parse_args()

    if args.transport == "stdio" and (args.host != "127.0.0.1" or args.port != 8001):
        print("Warning: --host and --port are ignored in STDIO mode", file=sys.stderr)

    if not config.MINERU_API_KEY:
        print(
            "Error: MINERU_API_KEY is required to start the service."
            "\\nSet the environment variable, for example:"
            "\\n  export MINERU_API_KEY='your_actual_api_key'"
            "\\nOr define it in the project root `.env` file."
            "\\n\\nUse --help to see available command-line options.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.output_dir:
        server.set_output_dir(args.output_dir)

    print("Starting MinerU file-to-Markdown service...")
    if args.transport in ["sse", "streamable-http"]:
        print(f"Server address: {args.host}:{args.port}")
    print("Press Ctrl+C to stop the service")

    server.run_server(mode=args.transport, port=args.port, host=args.host)


if __name__ == "__main__":
    main()
