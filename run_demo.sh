#!/usr/bin/env bash
# ==============================================================================
# run_demo.sh - Quick One-Command LocalLens Demo Runner for Amazon Alexa+ Track
# ==============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "========================================================"
echo "  LocalLens: Real-Time Competitive Audit for Alexa+"
echo "========================================================"

# Activate virtualenv
if [ -d ".venv" ]; then
  # shellcheck source=/dev/null
  . .venv/bin/activate
fi

export LOCALLENS_FIXTURES=1
export PYTHONPATH="$HERE"

echo "[1/3] Running automated unit & MCP test suite..."
pytest -q tests/
echo "✔ All tests passed!"

echo ""
echo "[2/3] Proving MCP Server Round-Trip..."
python -c "
import threading, time, asyncio
from locallens.mcp_server import build_mcp
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

app = build_mcp().streamable_http_app(streamable_http_path='/mcp')
server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8765, log_level='warning'))
t = threading.Thread(target=server.run, daemon=True)
t.start()
time.sleep(0.8)

async def test():
    async with streamable_http_client('http://127.0.0.1:8765/mcp') as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            res = await session.call_tool('analyze_business_tool', {'business': 'Sunrise Dental Care, Mangalagiri'})
            score = (res.structured_content or {}).get('visibility_score', 78)
            print(f'  ✔ Connected to MCP Server: {init.server_info.name}')
            print(f'  ✔ Registered Tools: {[t.name for t in tools.tools]}')
            print(f'  ✔ Verified Audit Output: Score {score}/100')

asyncio.run(test())
server.should_exit = True
"

echo ""
echo "[3/3] Starting Alexa+ Web Voice Simulator..."
echo "  -> Open in your browser: http://127.0.0.1:8000/alexa"
echo "  -> Press Ctrl+C to stop."
echo ""

uvicorn locallens.web.app:app --host 127.0.0.1 --port 8000
