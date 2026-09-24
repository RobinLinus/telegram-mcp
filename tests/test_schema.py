import datetime
import json
import inspect
from telethon.tl.alltlobjects import tlobjects
from telethon.tl import types, functions
from telegram_mcp.schema import REGISTRY, METHODS, TYPES, describe, decode, encode


def test_every_generated_constructor_is_represented_and_describable():
    assert len(REGISTRY) == len(tlobjects)
    for key, cls in REGISTRY.items():
        d = describe(key)
        assert d['name'] == key
        assert [p['name'] for p in d['parameters']] == list(inspect.signature(cls).parameters)
        json.dumps(d)
    assert len(METHODS) > 800
    assert len(TYPES) > 1600


def test_nested_roundtrip_preserves_wire_bytes():
    request = functions.messages.SendMessageRequest(
        peer=types.InputPeerUser(user_id=42, access_hash=2**63-2),
        message='Hello 🌍', random_id=2**63-3,
        entities=[types.MessageEntityBold(offset=0, length=5)])
    representation = json.loads(json.dumps(encode(request)))
    assert representation['random_id'] == {'$int': str(2**63-3)}
    assert bytes(decode(representation)) == bytes(request)


def test_message_patched_fields_and_special_types():
    message = types.Message(id=1, peer_id=types.PeerUser(42), message='example',
        date=datetime.datetime(2026,1,1,tzinfo=datetime.timezone.utc))
    assert decode(encode(message)).message == 'example'
    assert decode(encode(b'\x00\xff')) == b'\x00\xff'
    assert decode(encode(-(2**63))) == -(2**63)
