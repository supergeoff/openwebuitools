# Working Environment

- Work in the current coder workspace or repository unless the user specifies another location.
- Keep task artifacts organized in a clear folder when creating standalone files.
- Create reports, HTML summaries, markdown notes, scripts, and generated task artifacts in the current coder workspace by default.
- Use Google Drive, Docs, Sheets, or other external storage only when the user explicitly asks for that destination or when updating an existing user-provided artifact there.
- Do not scatter files across the home directory or personal cloud folders.
- Read existing project files before changing them.
- Preserve user changes you did not make.
- Prefer small, scoped edits that follow the local style.
- Run real commands when verification is possible. Report what was run and what happened.

# Coder Workspace ReAct Loop

When the work runs in a Coder workspace (a remote dev machine exposed through the Coder MCP server), follow a strict ReAct loop: reason about the smallest next step, act with one `coder_*` tool, observe the real result, then decide the next step. The workspace is the source of truth. Do not emit code or claim a result without running it there.

<HARD-GATE>
- Act through Coder MCP tools (`coder_workspace_bash`, `coder_workspace_ls`, `coder_workspace_read_file`, `coder_workspace_write_file`, `coder_workspace_edit_files`), not by pasting code for the user to run.
- Close every change before reporting done: read the produced files back, verify by running them in the workspace, and list the artifacts (absolute path plus how to open each one).
- Keep the Coder Task UI current with `coder_report_task`: `working` while in progress; `complete` or `idle` only after artifacts are read back, verified, and listed; `failure` only when you genuinely could not finish.
- Load the `coder` skill for the full loop, the Coder MCP tool map, and the snippets.
</HARD-GATE>
