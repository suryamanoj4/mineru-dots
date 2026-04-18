"""VParse File转Markdown服务的命令行界面。"""

import sys
import argparse

from . import config
from . import server


def main():
    """命令行界面的入口点。"""
    parser = argparse.ArgumentParser(description="VParse File转Markdown转换服务")

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

    # 验证API密钥 - 移动到这里，以便 --help 等参数可以无密钥运行
    if not config.VPARSE_API_KEY:
        print(
            "错误: 启动服务需要 VPARSE_API_KEY 环境变量。"
            "\\n请检查是否已设置该环境变量，例如："
            "\\n  export VPARSE_API_KEY='your_actual_api_key'"
            "\\n或者，确保在项目根目录的 `.env` 文件中定义了该变量。"
            "\\n\\n您可以使用 --help 查看可用的命令行选项。",
            file=sys.stderr,  # 将错误消息输出到 stderr
        )
        sys.exit(1)

    # Set output directory if provided
    if args.output_dir:
        server.set_output_dir(args.output_dir)

    # 打印配置信息
    print("VParse File转Markdown转换服务启动...")
    if args.transport in ["sse", "streamable-http"]:
        print(f"Server address: {args.host}:{args.port}")
    print("Press Ctrl+C to exit the service")

    server.run_server(mode=args.transport, port=args.port, host=args.host)


if __name__ == "__main__":
    main()
