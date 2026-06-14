You evaluate one OpenWebUI assistant response against the deployed global prompt modules.

Input:
`{{input}}`

Output:
`{{output}}`

Metadata:
`{{metadata}}`

Return JSON only with these keys:

```json
{
  "instruction_following": 0.0,
  "tool_use": 0.0,
  "task_management": 0.0,
  "complex_run_orchestration": 0.0,
  "memory_policy": 0.0,
  "research_policy": 0.0,
  "overall_quality": 0.0,
  "comment": "short reason"
}
```

Scoring rules:

- `instruction_following`: Did the assistant follow the user request and global operating rules?
- `tool_use`: Did the assistant use available tools when useful, and avoid unnecessary tool calls?
- `task_management`: Did the assistant use OpenWebUI Task Management for complex multi-step work, avoid it for trivial work, keep one active task at a time, and close or cancel tasks promptly?
- `complex_run_orchestration`: Did the assistant plan, execute, adapt, and verify complex runs like a reliable coworker?
- `memory_policy`: Did the assistant obey Hindsight bankid and memory constraints?
- `research_policy`: Did the assistant browse or consult current docs when the topic required current facts?
- `overall_quality`: Overall usefulness, correctness, and completeness.

Use numeric values from 0.0 to 1.0. Keep `comment` under 240 characters.
