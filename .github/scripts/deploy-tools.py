#!/usr/bin/env python3
import os
import re
import requests
import sys
from pathlib import Path


def get_installed_tools(base_url: str, headers: dict) -> list:
    resp = requests.get(
        f"{base_url}/api/v1/tools/",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    return []


def tool_exists(installed_tools: list, tool_id: str) -> bool:
    return any(t.get("id") == tool_id for t in installed_tools)


def parse_frontmatter(content: str) -> dict:
    """Parse the docstring frontmatter at the top of a Tool file.

    Returns a dict with keys like title, description, author, etc.
    """
    meta = {}
    # Look for a triple-quoted block at the very start of the file
    m = re.match(r'^[\'"""\'\']\'\'[\s\S]*?[\'"""\'\']', content)
    if not m:
        return meta
    block = m.group(0).strip('"\'').strip()
    for line in block.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def deploy_tool(base_url: str, api_key: str, tool_file: Path, installed_tools: list):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    tool_id = tool_file.stem

    with open(tool_file, "r") as f:
        content = f.read()

    meta = parse_frontmatter(content)
    name = meta.get("title") or tool_id.replace("_", " ").replace("-", " ").title()
    description = meta.get("description", "")

    payload = {
        "id": tool_id,
        "name": name,
        "content": content,
        "meta": {"description": description},
    }

    if tool_exists(installed_tools, tool_id):
        print(f"Tool '{tool_id}' already exists. Updating...")
        resp = requests.post(
            f"{base_url}/api/v1/tools/id/{tool_id}/update",
            headers=headers,
            json=payload,
            timeout=30,
        )
        action = "Updated"
    else:
        print(f"Creating tool '{tool_id}'...")
        resp = requests.post(
            f"{base_url}/api/v1/tools/create",
            headers=headers,
            json=payload,
            timeout=30,
        )
        action = "Created"

    if resp.status_code in (200, 201, 204):
        print(f"✅ {action} tool '{tool_id}'")
        return True

    print(
        f"❌ Failed to {action.lower()} tool '{tool_id}': {resp.status_code} {resp.text[:200]}..."
    )
    return False


def main():
    base_url = os.getenv("OPENWEBUI_URL", "http://localhost:3000").rstrip("/")
    api_key = os.getenv("OPENWEBUI_API_KEY")
    if not api_key:
        print("Error: OPENWEBUI_API_KEY environment variable is required.")
        sys.exit(1)

    tools_dir = Path("tools")
    if not tools_dir.exists():
        print("No tools/ directory found.")
        return

    headers = {"Authorization": f"Bearer {api_key}"}
    installed_tools = get_installed_tools(base_url, headers)

    success = True
    for py_file in tools_dir.glob("*.py"):
        try:
            print(f"Deploying {py_file.name}...")
            if deploy_tool(base_url, api_key, py_file, installed_tools):
                print(f"Successfully processed {py_file.name}")
            else:
                success = False
        except Exception as e:
            print(f"Error processing {py_file}: {e}")
            success = False

    if success:
        print("All tools deployed/updated successfully.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
