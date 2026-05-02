#!/usr/bin/env python3
import os
import requests
import sys
from pathlib import Path

def get_installed_functions(base_url: str, headers: dict) -> list:
    resp = requests.get(
        f"{base_url}/api/v1/functions/",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    return []

def filter_exists(installed_functions: list, filter_id: str) -> bool:
    return any(f.get("id") == filter_id for f in installed_functions)

def deploy_filter(base_url: str, api_key: str, filter_file: Path, installed_functions: list):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Get filter ID from filename
    filter_id = filter_file.stem
    
    with open(filter_file, "r") as f:
        content = f.read()
        
    payload = {
        "id": filter_id,
        "name": filter_id.capitalize(),
        "meta": {"description": f"Filter for {filter_id}"},
        "content": content,
        "is_active": True,
        "is_global": True
    }

    if filter_exists(installed_functions, filter_id):
        print(f"Filter '{filter_id}' already exists. Updating...")
        # Get existing function info
        existing = next(f for f in installed_functions if f.get("id") == filter_id)
        # Add id to payload for update
        payload["id"] = existing["id"]
        resp = requests.post(
            f"{base_url}/api/v1/functions/id/{filter_id}/update",
            headers=headers,
            json=payload,
            timeout=30,
        )
        action = "Updated"
    else:
        print(f"Creating filter '{filter_id}'...")
        resp = requests.post(
            f"{base_url}/api/v1/functions/create",
            headers=headers,
            json=payload,
            timeout=30,
        )
        action = "Created"

    if resp.status_code in (200, 201, 204):
        print(f"✅ {action} filter '{filter_id}'")
        return True

    print(f"❌ Failed to {action.lower()} filter '{filter_id}': {resp.status_code} {resp.text[:200]}...")
    return False

def main():
    base_url = os.getenv("OPENWEBUI_URL", "http://localhost:3000").rstrip("/")
    api_key = os.getenv("OPENWEBUI_API_KEY")
    if not api_key:
        print("Error: OPENWEBUI_API_KEY environment variable is required.")
        sys.exit(1)

    filter_dir = Path("filters")
    if not filter_dir.exists():
        print("No filters/ directory found.")
        return

    headers = {"Authorization": f"Bearer {api_key}"}
    installed_functions = get_installed_functions(base_url, headers)

    success = True
    for py_file in filter_dir.glob("*.py"):
        try:
            print(f"Deploying {py_file.name}...")
            if deploy_filter(base_url, api_key, py_file, installed_functions):
                print(f"Successfully processed {py_file.name}")
            else:
                success = False
        except Exception as e:
            print(f"Error processing {py_file}: {e}")
            success = False

    if success:
        print("All filters deployed/updated successfully.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
