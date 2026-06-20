---
name: coder
description: "Use when work runs inside a Coder workspace (a remote dev machine exposed through the Coder MCP server) to run, build, test, edit, debug, or serve code; enforces a deterministic ReAct loop (reason, act with one coder_* tool, observe the real result) and closes every change by reading the artifacts back, verifying them, and listing them."
tags: ["coder", "mcp", "react", "coding", "workspace", "artifacts", "determinism"]
---

# Coder Workspace ReAct Loop

Use this skill whenever code is executed or modified inside a Coder workspace
(github.com/coder/coder) reached through the Coder MCP server. Here "ReAct" means
Reason + Act (Thought -> Action -> Observation). It is not the JavaScript framework.

The workspace is a real remote machine and the single source of truth. Do not
reason about code you have not run there, and do not hand code to the user to run
themselves. Act through Coder MCP tools, observe the actual output, and report
only results you have verified in the workspace.

## Coder MCP tool map

One tool per step. Prefer the dedicated file tools over `coder_workspace_bash`
for reading, writing, listing, and editing files.

| Phase | Tool | Use for |
|---|---|---|
| Orient | `coder_get_authenticated_user` | Confirm identity before acting. |
| Orient | `coder_list_workspaces` | Find the target workspace. |
| Orient | `coder_get_workspace` | Resolve a workspace by name or ID and read its state. |
| Act (exec) | `coder_workspace_bash` | Run commands, scripts, installs, services, tests. |
| Act (read) | `coder_workspace_ls` | List directories. |
| Act (read) | `coder_workspace_read_file` | Read a file's contents. |
| Act (write) | `coder_workspace_write_file` | Create or overwrite a file (`content` is base64 bytes). |
| Act (write) | `coder_workspace_edit_file` / `coder_workspace_edit_files` | Edit one or more existing files. |
| Act (serve) | `coder_workspace_port_forward` | Expose a running port to reach a live artifact. |
| Act (serve) | `coder_workspace_list_apps` | List workspace apps. |
| Observe | `coder_get_workspace_agent_logs` / `coder_get_workspace_build_logs` | Inspect agent or build logs. |
| Report | `coder_report_task` | Push progress to the Coder Task UI. |

Background-task tools, when driving a long-running coding task instead of acting
directly: `coder_create_task`, `coder_list_tasks`, `coder_get_task_status`,
`coder_get_task_logs`, `coder_send_task_input`, `coder_delete_task`.

## The loop (mandatory order)

1. Orient. Resolve the workspace once and reuse that identifier for every call.
   `coder_workspace_bash` auto-starts a stopped workspace and waits for the agent,
   so you rarely need to start it manually.
2. Reason. State the smallest next step and the single tool that performs it.
   Keep reasoning short; plan only the next action in detail.
3. Act. Call exactly one `coder_*` tool. Never paste code for the user to run.
4. Observe. Read the real return value: stdout, exit code, file bytes, logs. If
   it failed, fix the cause and retry the same tool. Do not work around a failed
   file write with bash.
5. Repeat 2-4 until the change is implemented.
6. Close the loop (Artifact retrieval below). Only then report a finished state
   (`complete` or `idle`).

<HARD-GATE>
- Every claim about behavior must come from a tool result observed in this loop.
- One action per step. Do not batch unrelated actions or assume an outcome.
- File operations use the file tools, never `ls`/`cat`/`echo`/heredoc in bash.
- Do not report a finished state (`complete` or `idle`) until artifacts are read
  back, verified, and listed. Reserve `failure` for work you genuinely could not
  finish, and say what you tried and why.
</HARD-GATE>

## Workspace identifier

`coder_workspace_bash` and the file tools take a `workspace` parameter in any of
these formats:

- `workspace` (current user)
- `owner/workspace`
- `owner--workspace`
- `workspace.agent` or `owner/workspace.agent` (specific agent)

`coder_get_workspace` takes the name or ID as `workspace_id`. Resolve the target
once, then pass the same `workspace` value to every later call. `coder_workspace_bash`
also accepts `timeout_ms` (default 60000, max 300000) and `background: true` for
long-running services.

## Artifact retrieval (closing the loop)

An artifact is any file or output the work produced: source files, build outputs,
reports, logs, test results, generated data, running services. Before reporting
done, run these three steps in order:

1. Read back. Re-read each file you created or edited with
   `coder_workspace_read_file` (use `coder_workspace_ls` to confirm a tree).
   Check that the bytes on disk match what you intended.
2. Verify. Run it with `coder_workspace_bash`: execute the script, run the test
   suite, build the project, or curl the forwarded port. Capture the exit code
   and the key output. If the artifact is not executable, validate it another way
   and capture the result: parse, lint, or syntax-check it (for example
   `python -m json.tool`, `yq`, `tsc --noEmit`, `docker build`, a schema check).
   "Nothing to run" is not a reason to skip verification, and reading the bytes
   back is not verification. A change is not done until it is verified.
3. List. End your answer with an `Artifacts` section. For each artifact give its
   absolute path in the workspace, what it is, and how to open it: a command, a
   forwarded URL from `coder_workspace_port_forward`, or a workspace app from
   `coder_workspace_list_apps`.

Never describe an artifact you have not read back, and never report success on
code you have not run.

## Progress reporting

Keep the Coder Task UI accurate with `coder_report_task`, using the `state` field:

- `working`: report often, with a specific summary. Frequent updates are fine.
- `complete` or `idle`: a finished result. Only after artifacts are read back,
  verified, and listed. Never report either with unverified or unlisted artifacts.
- `failure`: only when you genuinely cannot finish. Say what you tried and why.

Good summaries name the concrete step ("Cloning <repo>", "Fixing the failing auth
test", "Running the test suite"). Bad summaries are vague ("working on it",
"trying to fix it").

## Snippets

Orient, then run the tests (one action per step):

```text
1. coder_get_workspace  { "workspace_id": "alice/dev-env" }
2. coder_workspace_bash { "workspace": "alice/dev-env", "command": "cd /home/coder/app && npm test", "timeout_ms": 120000 }
```

Write a file, then read it back and run it:

```text
1. coder_workspace_write_file { "workspace": "alice/dev-env", "path": "/home/coder/app/scripts/report.py", "content": "<base64 bytes>" }
2. coder_workspace_read_file  { "workspace": "alice/dev-env", "path": "/home/coder/app/scripts/report.py" }
3. coder_workspace_bash       { "workspace": "alice/dev-env", "command": "python /home/coder/app/scripts/report.py" }
```

Serve and expose a live artifact:

```text
1. coder_workspace_bash         { "workspace": "alice/dev-env", "command": "cd /home/coder/app && npm run dev", "background": true }
2. coder_workspace_port_forward { "workspace": "alice/dev-env", "port": 3000 }
```

Report progress around the work:

```text
coder_report_task { "summary": "Running the test suite", "state": "working" }
... act and observe ...
coder_report_task { "summary": "Tests green; report.csv generated and verified", "state": "complete" }
```

## Common mistakes

| Mistake | Fix |
|---|---|
| Pasting code for the user to run | Run it in the workspace with `coder_workspace_bash`. |
| Claiming success without running | Verify with a real command and capture the exit code. |
| Using `cat`/`echo`/heredoc for files | Use `coder_workspace_read_file` / `coder_workspace_write_file`. |
| Working around a failed write with bash | Fix the content or encoding and retry the file tool. |
| Re-resolving the workspace on every call | Resolve once, reuse the same identifier. |
| Ending on `complete` or `idle` early | Read back, verify, and list artifacts first. |
| Silent progress | Send `coder_report_task` `working` updates as you go. |

## Out of scope

- Local code execution outside a Coder workspace; use the normal coding tools.
- Template authoring (`coder_create_template`, `coder_create_template_version`,
  `coder_upload_tar_file`) unless the user explicitly asks to manage templates.
