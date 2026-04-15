#!/usr/bin/env python3
import os
import json
import requests
import sys
from pathlib import Path


def deploy_model(base_url: str, api_key: str, model_data: dict or list):
    """Deploy model preset (matches /api/v1/models/create from Swagger)."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    # From Swagger: POST /api/v1/models/create is best (ModelForm with id/name/params/meta). 401=bad key, 422=bad payload.
    endpoints = [
        f"{base_url}/api/v1/models/create"
    ]  # Prioritized per openapi.json analysis
    for endpoint in endpoints:
        try:
            payload = model_data[0] if isinstance(model_data, list) else model_data
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            if resp.status_code in (200, 201, 204):
                print(f"✅ Deployed to {endpoint}")
                return True
            print(f"❌ {endpoint} returned {resp.status_code}: {resp.text[:200]}...")
        except Exception as e:
            print(f"Error with {endpoint}: {e}")
    print(
        "Failed. Set OPENWEBUI_URL and valid API key."
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
