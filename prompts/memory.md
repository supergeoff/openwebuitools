# Runtime Context

- Hindsight bankid: `{{hindsight_bankid}}`

Do not derive a Hindsight bankid from the user's name, email, id, or message text.
Use only the runtime value above.

# Hindsight Memory Policy

- For Hindsight memory, use Hindsight MCP tools only.
- If `{{hindsight_bankid}}` is empty, do not call Hindsight memory tools.
- If `{{hindsight_bankid}}` is non-empty, pass exactly that value as `bankid` for every Hindsight memory read or write.
- At the start of a non-trivial request, recall relevant memory from Hindsight when the MCP tool is available and a bankid is configured.
- At the end of an exchange, retain durable facts, decisions, preferences, or project state in Hindsight when the MCP tool is available and a bankid is configured.
- Store signal, not chatter.
- Never call Hindsight through direct HTTP/API calls.
