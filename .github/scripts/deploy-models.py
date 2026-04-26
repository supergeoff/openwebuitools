#!/usr/bin/env python3
import os
import json
import requests
import sys
from pathlib import Path


def model_exists(base_url: str, headers: dict, model_id: str) -> bool:
    resp = requests.get(
        f"{base_url}/api/v1/models/model",
        headers=headers,
        params={"id": model_id},
        timeout=30,
    )
    return resp.status_code == 200


def deploy_model(base_url: str, api_key: str, model_data: dict or list):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = model_data[0] if isinstance(model_data, list) else model_data
    model_id = payload.get("id")

    if model_id and model_exists(base_url, headers, model_id):
        print(f"Model '{model_id}' already exists. Updating...")
        resp = requests.post(
            f"{base_url}/api/v1/models/model/update",
            headers=headers,
            json=payload,
            timeout=30,
        )
        action = "Updated"
    else:
        print(f"Creating model '{model_id}'...")
        resp = requests.post(
            f"{base_url}/api/v1/models/create",
            headers=headers,
            json=payload,
            timeout=30,
        )
        action = "Created"

    if resp.status_code in (200, 201, 204):
        print(f"✅ {action} model '{model_id}'")
        return True

    print(
        f"❌ Failed to {action.lower()} model '{model_id}': {resp.status_code} {resp.text[:200]}..."
    )
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
                print(f"Successfully processed {json_file.name}")
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
