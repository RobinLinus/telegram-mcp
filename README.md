# Telegram user MCP

A local desktop plugin exposing all **823 RPC methods and 1,700 constructors in Telegram API layer 229**, through Telethon 1.45.0. Acts as your Telegram user. No hosted backend, Bot API, message polling, or OpenAI API key.

## Configuration

The server reads `~/.config/telegram-mcp/config.json` by default. Set `TELEGRAM_CONFIG_PATH` to use a different file. Individual environment variables override corresponding file entries:

| Environment variable | Config key |
| --- | --- |
| `TELEGRAM_API_ID` | `api_id` |
| `TELEGRAM_API_HASH` | `api_hash` |
| `TELEGRAM_SESSION_PATH` | `session_path` |

Example (placeholders only):

```json
{"api_id": 12345, "api_hash": "YOUR_API_HASH", "session_path": "/absolute/private/telegram.session"}
```

Keep the directory private and files mode 0600. Session keys give account access. The server never returns configuration or session keys from its status tool. Raw API operations may themselves return sensitive data, just as in Telegram's API.

The desktop's **Settings → MCP servers** supports a local STDIO entry. For explicit per-server environment configuration, the shared desktop config supports:

```toml
[mcp_servers.telegram]
command = "/absolute/path/to/python"
args = ["-m", "telegram_mcp.server"]

[mcp_servers.telegram.env]
TELEGRAM_CONFIG_PATH = "/absolute/private/config.json"
# Alternatively define TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_PATH.
```

Use either the installed plugin or a direct MCP entry, not both for the same session. A dedicated credentials form for bundled plugins is not assumed. With the installed plugin, edit the private JSON config or configure environment variables in the host; restart its MCP process after changes.

## Development

Python 3.11+ is required.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e . pytest pytest-asyncio
.venv/bin/python -m pytest -q
.venv/bin/python scripts/smoke.py
```

Import an existing compatible Telethon client without displaying secrets:

```sh
.venv/bin/python scripts/setup.py import --source /path/to/client/.local --config ~/.config/telegram-mcp/config.json
```

The source must contain `credentials.json` with `api_id`/`api_hash`, and `reader.session`. The import takes a consistent SQLite backup into a separate session file. The existing client remains unchanged. A copied session retains the same Telegram authorization, so revocation affects both copies. Do not use copies on different hosts/IPs concurrently. To obtain an independent authorization, configure a new session path and run:

```sh
.venv/bin/python scripts/setup.py login
```

Credentials, session databases, and results must never enter the plugin package. During initial development this project's `.local/config.json` is used by setting `TELEGRAM_CONFIG_PATH` explicitly.

## Desktop installation

The personal plugin installer creates an independent runtime, copies only an explicit package allowlist, registers the personal marketplace entry through the plugin-creator helper, and installs it with the desktop CLI:

```sh
.venv/bin/python scripts/install.py --plugin-skill /path/to/plugin-creator
```

The setup helper is also usable independently. The plugin starts `scripts/run.sh` over stdio; its runtime defaults to `~/.local/share/telegram-mcp/venv/bin/python`, overridable with `TELEGRAM_MCP_PYTHON`. Open a new desktop task after installing so it discovers the tools.

## API use

Convenience tools `list_chats`, `get_messages`, `search_messages`, and `send_message` cover common workflows. `send_message` requires an explicit stable random ID for Telegram deduplication.

1. `search_api` searches the complete method/type registry, with pagination.
2. `describe_api` returns parameters, type annotations, optionality, return documentation, and possible result constructors.
3. `resolve_peer` yields an InputPeer for usernames, IDs, or `self`.
4. `invoke_api` constructs and invokes any generated method. Telegram enforces user/bot, admin, premium, payment, region, and other eligibility restrictions.
5. `upload_file` returns InputFile constructors usable in media RPCs; `download_file` downloads a supplied InputFileLocation to a new local file.
6. `read_result` retrieves large responses in chunks, with no silent truncation.
7. `get_status` verifies the live account without returning credentials.

TL constructor format: `{"_":"InputPeerSelf"}`. Nested objects and vectors are recursive. Bytes use `{"$bytes":"base64"}`, large integers use `{"$int":"decimal"}`, timestamps use `{"$datetime":"ISO8601"}`. Ordinary safe integers remain JSON numbers.

Example raw history request:

```json
{"method":"messages.GetHistoryRequest","parameters":{"peer":{"_":"InputPeerSelf"},"offset_id":0,"offset_date":null,"add_offset":0,"limit":20,"max_id":0,"min_id":0,"hash":0}}
```

Pagination and update state are method-specific. Agents can retain offsets/message IDs, or use updates.GetState/GetDifference and channel difference methods to account for edits and deletions. No automatic polling occurs. Connection housekeeping while the server is alive is handled by Telethon.

## Reliability and scope

RPC flood waits return structured error information including wait seconds. Application request retries are disabled. Keep `random_id` stable across logical-send retries; uncertain non-idempotent outcomes require checking state before repeating. Expired media file references require fetching the originating message again. Tools do not bypass the host's approval policy. The generic RPC tool is explicitly write-capable and potentially destructive.

Coverage means all generated RPCs and constructors in the pinned layer, not every future Telegram layer. It includes call and encrypted-chat RPCs, but does not provide a voice/video media engine or the client-side secret-chat encryption state machine. Login codes and 2FA are handled through interactive setup; API methods that require those values are still present in the schema.

Large results are stored privately in `results/` beside the session and persist until deleted locally. Neither tests nor smoke checks send messages. `scripts/smoke.py --live` checks authorization and reads one Saved Messages history page without printing messages.

## Updating Telegram layers

Update the Telethon pin, regenerate `requirements.lock`, and run the coverage test plus MCP/live smoke checks. The registry is derived from the installed generated classes, so method parameters and constructors cannot drift from the runtime. Changes to client-side serialization still require review. The registry test proves exposure, not live eligibility or successful execution of every RPC.
