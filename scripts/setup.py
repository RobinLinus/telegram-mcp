#!/usr/bin/env python3
"""Import existing credentials locally or authenticate interactively; never print secrets."""
import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import sqlite3


def import_config(source, destination, credentials_name="credentials.json", session_name="reader.session"):
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise ValueError('Destination config already exists; refusing to overwrite')
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    credentials = json.loads((source / credentials_name).read_text())
    session = destination.parent / 'telegram.session'
    if session.exists():
        raise ValueError('Destination session already exists')
    original = sqlite3.connect((source / session_name).resolve().as_uri()+'?mode=ro', uri=True)
    target = sqlite3.connect(session)
    try:
        original.backup(target)
    finally:
        original.close()
        target.close()
    os.chmod(session, 0o600)
    data = {'api_id': int(credentials['api_id']), 'api_hash': credentials['api_hash'],
            'session_path': str(session)}
    with destination.open('x') as f:
        json.dump(data, f, indent=2)
    os.chmod(destination, 0o600)
    print('Imported API credentials and existing session; secrets were not displayed.')


async def login():
    from telegram_mcp.config import load
    from telethon import TelegramClient
    cfg = load()
    c = TelegramClient(cfg['session_path'], cfg['api_id'], cfg['api_hash'])
    try:
        await c.start(phone=lambda: input('Phone number: '),
                      password=lambda: getpass.getpass('Telegram 2FA password: '),
                      code_callback=lambda: getpass.getpass('Telegram login code: '))
        print('Telegram session authorized.')
    finally:
        await c.disconnect()


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='action', required=True)
    imp = sub.add_parser('import')
    imp.add_argument('--source', type=Path, required=True)
    imp.add_argument('--config', type=Path, default=Path('~/.config/telegram-mcp/config.json'))
    imp.add_argument('--credentials-name', default='credentials.json')
    imp.add_argument('--session-name', default='reader.session')
    sub.add_parser('login')
    a = p.parse_args()
    if a.action == 'import':
        import_config(a.source, a.config, a.credentials_name, a.session_name)
    else:
        asyncio.run(login())

if __name__ == '__main__':
    main()
