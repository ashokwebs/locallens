"""Call the LocalLens MCP server over Streamable HTTP (start it first: python -m locallens.mcp_server)."""
import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/mcp"
BUSINESS = sys.argv[2] if len(sys.argv) > 2 else "Sunrise Dental Care, Mangalagiri"  # fixture name; pass a real one in live mode


async def main() -> None:
    async with streamable_http_client(URL) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("server:", init.server_info.name, "| protocol:", init.protocol_version)
            tools = await session.list_tools()
            print("tools:", [t.name for t in tools.tools])
            res = await session.call_tool("analyze_business_tool", {"business": BUSINESS})
            payload = res.structured_content or json.loads(res.content[0].text)
            print("score:", payload.get("visibility_score"), "| first fix:", payload["top_fixes"][0]["title"])


asyncio.run(main())
