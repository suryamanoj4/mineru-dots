"""演示如何使用 VParse File转Markdown客户端的示例。"""

import os
import asyncio
from mcp.client import MCPClient


async def convert_file_url_example():
    """Example of converting a file from a URL."""
    client = MCPClient("http://localhost:8000")

    # Convert a single file URL
    result = await client.call(
        "convert_file_url", url="https://example.com/sample.pdf", enable_ocr=True
    )
    print(f"Conversion result: {result}")

    # Convert multiple file URLs
    urls = """
    https://example.com/doc1.pdf
    https://example.com/doc2.pdf
    """
    result = await client.call("convert_file_url", url=urls, enable_ocr=True)
    print(f"Multiple conversion results: {result}")


async def convert_file_file_example():
    """Example of converting a local file."""
    client = MCPClient("http://localhost:8000")

    # Get absolute path of the test file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
    test_file_path = os.path.join(project_root, "test_files", "test.pdf")

    # Convert a single local file
    result = await client.call(
        "convert_file_file", file_path=test_file_path, enable_ocr=True
    )
    print(f"File conversion result: {result}")


async def get_api_status_example():
    """Example of retrieving API status."""
    client = MCPClient("http://localhost:8000")

    # Get API status
    status = await client.get_resource("status://api")
    print(f"API Status: {status}")

    # Get usage help
    help_text = await client.get_resource("help://usage")
    print(f"Usage help: {help_text[:100]}...")  # Show first 100 characters


async def main():
    """Run all examples."""
    print("Running File to Markdown conversion examples...")

    # 检查是否设置了 API_KEY
    if not os.environ.get("VPARSE_API_KEY"):
        print("警告: VPARSE_API_KEY 环境变量未设置。")
        print("使用以下命令设置: export VPARSE_API_KEY=your_api_key")
        print("跳过需要 API 访问的示例...")

        # Only get API status
        await get_api_status_example()
    else:
        # Run all examples
        await convert_file_url_example()
        await convert_file_file_example()
        await get_api_status_example()


if __name__ == "__main__":
    asyncio.run(main())
