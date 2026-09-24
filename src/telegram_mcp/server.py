"""On-demand Telegram RPC. No message polling, no autonomous writes."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from contextlib import asynccontextmanager
from telethon import TelegramClient, errors
from telethon.tl.alltlobjects import LAYER
from mcp.server.fastmcp import FastMCP
from .config import load
from .schema import REGISTRY, METHODS, TYPES, describe, decode, encode

client = None
lock = asyncio.Lock()

@asynccontextmanager
async def lifespan(server):
    yield {}
    if client and client.is_connected():
        await client.disconnect()

mcp = FastMCP('Telegram user', lifespan=lifespan)

async def connection():
    global client
    async with lock:
        if client is None:
            cfg = load()
            client = TelegramClient(cfg['session_path'], cfg['api_id'], cfg['api_hash'],
                receive_updates=False, flood_sleep_threshold=0, request_retries=0,
                connection_retries=2, timeout=15)
        if not client.is_connected():
            await client.connect()
        if not await client.is_user_authorized():
            raise ValueError('Telegram session is not authorized. Run scripts/setup.py login locally.')
    return client

READ = {'readOnlyHint': True, 'openWorldHint': True}
WRITE = {'readOnlyHint': False, 'destructiveHint': True, 'idempotentHint': False, 'openWorldHint': True}

@mcp.tool(annotations=READ)
def search_api(query: str = '', kind: str = 'all', offset: int = 0, limit: int = 40) -> dict:
    """Search ALL generated Telegram methods/types by name. Names use Telethon casing, e.g. messages.GetHistoryRequest. Empty query lists all. No bot-only filtering."""
    if kind not in ('all', 'method', 'type') or offset < 0 or not 1 <= limit <= 100:
        raise ValueError('Invalid kind, offset, or limit')
    source = METHODS if kind == 'method' else TYPES if kind == 'type' else REGISTRY
    terms = query.lower().split()
    found = sorted(n for n in source if all(t in n.lower() for t in terms))
    return {'layer': LAYER, 'total': len(found), 'names': found[offset:offset+limit],
            'next_offset': offset+limit if offset+limit < len(found) else None}

@mcp.tool(annotations=READ)
def describe_api(name: str) -> dict:
    """Get constructor parameters and annotations. Use nested {'_': 'ConstructorName', ...} objects; tagged $int/$bytes/$datetime values preserve exact types."""
    return describe(name)

@mcp.tool(annotations=WRITE)
async def invoke_api(method: str, parameters: dict) -> dict:
    """Invoke ANY registered Telegram RPC as the logged-in user, including destructive/admin/payment/account methods. Obtain user authorization appropriate to effects. Telegram determines eligibility. Never pass login secrets here. No automatic application retries; retain random_id when retrying sends."""
    if method not in METHODS:
        raise ValueError('Unknown method; use search_api')
    request = METHODS[method](**{k: decode(v) for k,v in parameters.items()})
    c = await connection()
    try:
        result = encode(await c(request))
    except errors.RPCError as e:
        return {'ok': False, 'error': type(e).__name__, 'code': e.code,
                'message': e.message, 'retry_after_seconds': getattr(e, 'seconds', None)}
    return store_result(result)


def store_result(result):
    raw = json.dumps(result, ensure_ascii=False)
    if len(raw) <= 40000:
        return {'ok': True, 'result': result}
    root = Path(load()['session_path']).parent / 'results'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    ident = hashlib.sha256(raw.encode()).hexdigest()
    dest = root / (ident + '.json')
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(raw)
    return {'ok': True, 'result_handle': ident, 'characters': len(raw), 'read_with': 'read_result'}

@mcp.tool(annotations=READ)
def read_result(handle: str, offset: int = 0, limit: int = 20000) -> dict:
    """Read a character slice of a large JSON response. Concatenate chunks before parsing. Results persist beside the session."""
    if len(handle)!=64 or any(c not in '0123456789abcdef' for c in handle) or offset<0 or not 1<=limit<=40000:
        raise ValueError('Invalid handle or range')
    raw = (Path(load()['session_path']).parent / 'results' / (handle+'.json')).read_text()
    return {'text': raw[offset:offset+limit], 'next_offset': offset+limit if offset+limit<len(raw) else None}

@mcp.tool(annotations=READ)
async def resolve_peer(peer: str) -> dict:
    """Resolve username, phone, self, or signed Telegram peer ID into a reusable InputPeer constructor."""
    c = await connection()
    return encode(await c.get_input_entity(int(peer) if peer.lstrip('-').isdigit() else peer))

@mcp.tool(annotations=READ)
async def get_status() -> dict:
    """Check live authorization and identity without exposing credentials."""
    c = await connection()
    me = await c.get_me()
    return {'authorized': True, 'user_id': str(me.id), 'username': me.username, 'api_layer': LAYER,
            'methods': len(METHODS), 'types': len(TYPES)}

@mcp.tool(annotations=READ)
async def list_chats(limit: int = 30, offset_id: int = 0,
                     offset_date: str | None = None, offset_peer: dict | None = None) -> dict:
    """List conversations. For the next page supply the last dialog's top message ID/date and resolved peer."""
    if not 1 <= limit <= 100:
        raise ValueError('limit must be 1..100')
    return await invoke_api('messages.GetDialogsRequest', {
        'offset_date': {'$datetime': offset_date} if offset_date else None,
        'offset_id': offset_id, 'offset_peer': offset_peer or {'_': 'InputPeerEmpty'},
        'limit': limit, 'hash': 0})

@mcp.tool(annotations=READ)
async def get_messages(peer: str, limit: int = 30, before_id: int = 0, after_id: int = 0) -> dict:
    """Read chat history without marking it read. before_id pages older messages; after_id filters newer messages."""
    if not 1 <= limit <= 100:
        raise ValueError('limit must be 1..100')
    return await invoke_api('messages.GetHistoryRequest', {
        'peer': await resolve_peer(peer), 'offset_id': before_id, 'offset_date': None,
        'add_offset': 0, 'limit': limit, 'max_id': 0, 'min_id': after_id, 'hash': 0})

@mcp.tool(annotations=READ)
async def search_messages(peer: str, query: str, limit: int = 30, before_id: int = 0) -> dict:
    """Search message text in a chat, paging backwards with before_id. Raw search methods support further filters and global search."""
    if not 1 <= limit <= 100:
        raise ValueError('limit must be 1..100')
    return await invoke_api('messages.SearchRequest', {
        'peer': await resolve_peer(peer), 'q': query, 'filter': {'_': 'InputMessagesFilterEmpty'},
        'min_date': None, 'max_date': None, 'offset_id': before_id, 'add_offset': 0,
        'limit': limit, 'max_id': 0, 'min_id': 0, 'hash': 0})

@mcp.tool(annotations=WRITE)
async def send_message(peer: str, message: str, random_id: str, reply_to_message_id: int | None = None) -> dict:
    """Send text as the user. Supply a unique signed 64-bit decimal random_id per logical message and reuse it on retries to allow Telegram deduplication. Sending requires user instruction."""
    ident = int(random_id)
    if not -(2**63) <= ident < 2**63:
        raise ValueError('random_id must be a signed 64-bit integer')
    params = {'peer': await resolve_peer(peer), 'message': message, 'random_id': {'$int': str(ident)}}
    if reply_to_message_id is not None:
        params['reply_to'] = {'_': 'InputReplyToMessage', 'reply_to_msg_id': reply_to_message_id}
    result = await invoke_api('messages.SendMessageRequest', params)
    return {**result, 'random_id': str(ident)}

@mcp.tool(annotations=WRITE)
async def upload_file(path: str) -> dict:
    """Upload a local file to Telegram; returns temporary InputFile for raw sendMedia/profile RPCs. Does not send a message."""
    c = await connection()
    return encode(await c.upload_file(str(Path(path).expanduser().resolve(strict=True))))

@mcp.tool(annotations=WRITE)
async def download_file(location: dict, path: str) -> dict:
    """Download a Telegram InputFileLocation to a new local path. Refuses overwrites. Use raw message media fields to construct the location."""
    c = await connection()
    dest = Path(path).expanduser()
    with dest.open('xb') as f:
        os.chmod(dest, 0o600)
        await c.download_file(decode(location), file=f)
    return {'path': str(dest.resolve()), 'bytes': dest.stat().st_size}

def main():
    os.umask(0o077)
    mcp.run(transport='stdio')

if __name__ == '__main__':
    main()
