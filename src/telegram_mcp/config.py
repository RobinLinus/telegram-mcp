import json
import os
from pathlib import Path


def load():
    path = Path(os.environ.get('TELEGRAM_CONFIG_PATH', '~/.config/telegram-mcp/config.json')).expanduser()
    data = json.loads(path.read_text()) if path.exists() else {}
    for key in ('api_id', 'api_hash', 'session_path'):
        if 'TELEGRAM_' + key.upper() in os.environ:
            data[key] = os.environ['TELEGRAM_' + key.upper()]
    missing = [k for k in ('api_id', 'api_hash', 'session_path') if not data.get(k)]
    if missing:
        raise ValueError('Missing configuration: ' + ', '.join(missing))
    data['api_id'] = int(data['api_id'])
    data['session_path'] = str(Path(data['session_path']).expanduser())
    return data
