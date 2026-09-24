"""Real stdio MCP check; --live adds only account status and Saved Messages history reads."""
import asyncio
import json
import os
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    root = Path(__file__).resolve().parent.parent
    installed = os.environ.get('MCP_PLUGIN_ROOT')
    params = (StdioServerParameters(command='sh', args=[str(Path(installed)/'scripts/run.sh')], env=dict(os.environ))
        if installed else StdioServerParameters(command=sys.executable, args=['-m','telegram_mcp.server'], env={
        **os.environ, 'PYTHONPATH':str(root/'src')}))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            assert 'invoke_api' in [t.name for t in listed.tools]
            result = await session.call_tool('search_api', {'query':'GetHistory', 'kind':'method'})
            assert not result.isError
            print('MCP initialization, discovery and schema search passed; tools:', len(listed.tools))
            if '--live' in sys.argv:
                status = await session.call_tool('get_status', {})
                if status.isError:
                    raise RuntimeError('Live status failed: '+str(status.content))
                print('Live Telegram authorization check passed (identity omitted).')
                history = await session.call_tool('invoke_api', {'method':'messages.GetHistoryRequest','parameters':{
                    'peer':{'_':'InputPeerSelf'},'offset_id':0,'offset_date':None,'add_offset':0,
                    'limit':1,'max_id':0,'min_id':0,'hash':0}})
                assert not history.isError
                payload = history.structuredContent or json.loads(history.content[0].text)
                assert payload and payload.get('ok'), 'Telegram read failed'
                print('Raw Saved Messages history RPC passed (message content omitted).')

asyncio.run(main())
