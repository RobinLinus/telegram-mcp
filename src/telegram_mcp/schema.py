"""Registry and lossless JSON codec for every generated Telegram TL constructor."""
import base64
import datetime
import inspect
from telethon.tl.alltlobjects import tlobjects, LAYER
from telethon.tl.tlobject import TLRequest, TLObject


def name(cls):
    module = cls.__module__.split('.')
    category = 'functions' if issubclass(cls, TLRequest) else 'types'
    if cls.__module__ == 'telethon.tl.patched':
        return cls.__name__
    index = module.index(category)
    return '.'.join(module[index + 1:] + [cls.__name__])

REGISTRY = {name(cls): cls for cls in tlobjects.values()}
METHODS = {n: c for n, c in REGISTRY.items() if issubclass(c, TLRequest)}
TYPES = {n: c for n, c in REGISTRY.items() if not issubclass(c, TLRequest)}


def describe(key):
    cls = REGISTRY[key]
    return {'name': key, 'kind': 'method' if cls in METHODS.values() else 'type',
            'layer': LAYER, 'constructor_id': hex(cls.CONSTRUCTOR_ID),
            'parameters': [{'name': p.name, 'required': p.default is inspect.Parameter.empty,
                'annotation': str(p.annotation) if p.annotation is not inspect.Parameter.empty else None,
                'default': encode(p.default) if p.default is not inspect.Parameter.empty else None}
                for p in inspect.signature(cls).parameters.values()],
            'returns': inspect.getdoc(cls.__init__),
            'result_constructors': sorted(n for n, c in TYPES.items()
                if c.SUBCLASS_OF_ID == cls.SUBCLASS_OF_ID),
            'documentation': 'https://tl.telethon.dev/'}


def decode(value):
    if isinstance(value, list):
        return [decode(x) for x in value]
    if not isinstance(value, dict):
        return value
    if '$bytes' in value:
        return base64.b64decode(value['$bytes'], validate=True)
    if '$int' in value:
        return int(value['$int'])
    if '$datetime' in value:
        return datetime.datetime.fromisoformat(value['$datetime'])
    if '_' not in value:
        return {k: decode(v) for k, v in value.items()}
    cls = REGISTRY[value['_']]
    return cls(**{k: decode(v) for k, v in value.items() if k != '_'})


def encode(value):
    if isinstance(value, TLObject):
        fields = inspect.signature(type(value)).parameters
        return {'_': name(type(value)), **{k: encode(getattr(value, k)) for k in fields if hasattr(value, k)}}
    if isinstance(value, bytes):
        return {'$bytes': base64.b64encode(value).decode()}
    if isinstance(value, datetime.datetime):
        return {'$datetime': value.isoformat()}
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53 - 1:
        return {'$int': str(value)}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    return value
