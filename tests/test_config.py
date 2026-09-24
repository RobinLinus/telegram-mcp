import json
import pytest
from telegram_mcp.config import load


def test_environment_overrides_file(tmp_path, monkeypatch):
    p = tmp_path/'config.json'
    p.write_text(json.dumps({'api_id':1,'api_hash':'test-only','session_path':str(tmp_path/'session')}))
    monkeypatch.setenv('TELEGRAM_CONFIG_PATH',str(p))
    monkeypatch.setenv('TELEGRAM_API_ID','2')
    monkeypatch.setenv('TELEGRAM_API_HASH','override-test-only')
    assert load()['api_id']==2
    assert load()['api_hash']=='override-test-only'


def test_missing_configuration_errors_without_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv('TELEGRAM_CONFIG_PATH',str(tmp_path/'absent'))
    for key in ('API_ID','API_HASH','SESSION_PATH'):
        monkeypatch.delenv('TELEGRAM_'+key,raising=False)
    with pytest.raises(ValueError, match='Missing configuration'):
        load()
