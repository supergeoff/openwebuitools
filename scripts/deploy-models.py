#!/usr/bin/env python3
import os
import json
import requests
import sys
from pathlib import Path


def deploy_model(base_url: str, api_key: str, model_data: dict or list):
    """Deploy or update model using OpenWebUI API."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    # Updated endpoints for model presets (405=method not supported, 422=invalid payload for that route).
    # For this JSON format (DB record with base_model_id), use UI "Add Model" or custom admin endpoint. /functions/create expects Pipe definition.
    # Try your instance's admin API or convert to Pipe for automatic deployment (see docs/08-pipes.md, 14-development-debugging.md).
    endpoints = [
        f"{base_url}/api/v1/models",
        f"{base_url}/api/v1/admin/models",
        f"{base_url}/api/v1/admin/models/create",
        f"{base_url}/api/v1/models/create",
        f"{base_url}/api/v1/functions/create",
    ]
    for endpoint in endpoints:
        try:
            if isinstance(model_data, list):
                payload = model_data[0] if model_data else {}
            else:
                payload = model_data
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            if resp.status_code in (200, 201, 204):
                print(f"✅ Deployed to {endpoint}")
                return True
            elif resp.status_code < 500:
                print(f"⚠️  {endpoint} returned {resp.status_code}")
                continue
        except Exception as e:
            print(f"Error with {endpoint}: {e}")
            continue
    print("❌ Failed to deploy on all endpoints. Check OPENWEBUI_URL and API key.")
    return False


def main():
    base_url = os.getenv("OPENWEBUI_URL", "http://localhost:3000").rstrip("/")
    api_key = os.getenv("OPENWEBUI_API_KEY")
    if not api_key:
        print("Error: OPENWEBUI_API_KEY environment variable is required.")
        sys.exit(1)

    models_dir = Path("models")
    if not models_dir.exists():
        print("No models/ directory found.")
        return

    success = True
    for json_file in models_dir.glob("*.json"):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            print(f"Deploying {json_file.name}...")
            if deploy_model(base_url, api_key, data):
                print(f"✅ Successfully processed {json_file.name}")
            else:
                success = False
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            success = False

    if success:
        print("All models deployed/updated successfully.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
