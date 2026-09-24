import json
import pytest
from telethon import errors
from telethon.tl import types
from telegram_mcp import server


def test_search_pagination_and_validation():
    page = server.search_api('messages', 'method', limit=3)
    assert len(page['names']) == 3
    assert page['next_offset'] == 3
    assert not set(page['names']) & set(server.search_api('messages', 'method', offset=3, limit=3)['names'])
    with pytest.raises(ValueError):
        server.search_api(limit=-1)


@pytest.mark.asyncio
async def test_raw_call_dispatch_and_flood_wait(monkeypatch):
    class Fake:
        async def __call__(self, request):
            assert type(request).__name__ == 'GetStateRequest'
            raise errors.FloodWaitError(request, capture=27)
    async def connection(): return Fake()
    monkeypatch.setattr(server, 'connection', connection)
    result = await server.invoke_api('updates.GetStateRequest', {})
    assert result['retry_after_seconds'] == 27
    assert not result['ok']


def test_overflow_is_complete_and_paths_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'load', lambda: {'session_path': str(tmp_path/'session')})
    value = {'large': '🌍'*41000}
    result = server.store_result(value)
    chunks = []
    offset = 0
    while offset is not None:
        part = server.read_result(result['result_handle'], offset=offset)
        chunks.append(part['text'])
        offset = part['next_offset']
    assert json.loads(''.join(chunks)) == value
    with pytest.raises(ValueError): server.read_result('../secrets')


@pytest.mark.asyncio
async def test_read_write_annotations():
    tools = {t.name:t for t in await server.mcp.list_tools()}
    assert tools['invoke_api'].annotations.readOnlyHint is False
    assert tools['invoke_api'].annotations.destructiveHint is True
    assert tools['get_status'].annotations.readOnlyHint is True

@pytest.mark.asyncio
async def test_convenience_requests_are_valid_and_send_id_is_stable(monkeypatch):
    from telegram_mcp.schema import METHODS, decode
    captured = []
    async def invoke(method, parameters):
        request = METHODS[method](**{k:decode(v) for k,v in parameters.items()})
        bytes(request)
        captured.append(request)
        return {'ok':True, 'result':{}}
    async def resolve(peer): return {'_':'InputPeerSelf'}
    monkeypatch.setattr(server, 'invoke_api', invoke)
    monkeypatch.setattr(server, 'resolve_peer', resolve)
    await server.list_chats()
    await server.get_messages('self', after_id=20)
    assert captured[-1].min_id == 20
    await server.search_messages('self', 'hello')
    result = await server.send_message('self', 'hello', '9223372036854775806', reply_to_message_id=1)
    assert result['random_id'] == '9223372036854775806'
    assert captured[-1].random_id == 9223372036854775806
    assert captured[-1].reply_to.reply_to_msg_id == 1
    # These calls only construct and serialize requests. No live write is performed.
