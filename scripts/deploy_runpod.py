import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
if not RUNPOD_API_KEY:
    raise ValueError("RUNPOD_API_KEY is not set in environment.")

RUNPOD_API_URL = "https://api.runpod.io/graphql"

def create_pod():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }

    # Example GraphQL mutation to create a new pod
    query = """
    mutation CreatePod($input: PodInsertInput!) {
      podCreate(input: $input) {
        id
        desiredStatus
        imageName
        env
      }
    }
    """

    # Variables for a template using Docker compose or a single container
    # Assuming using a custom template or direct docker image
    variables = {
        "input": {
            "name": "guestFlow-agent-gpu",
            "imageName": "your-docker-hub/guestflow-agent:latest",
            "gpuCount": 1,
            "gpuTypeId": "NVIDIA GeForce RTX 4090",
            "cloudType": "SECURE",
            "containerDiskInGb": 50,
            "volumeInGb": 50,
            "env": [
                {"key": "RUNPOD_API_KEY", "value": RUNPOD_API_KEY},
            ],
            "ports": "8000/http"
        }
    }

    payload = {
        "query": query,
        "variables": variables
    }

    response = requests.post(RUNPOD_API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        print("Pod deployment initiated successfully.")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Failed to deploy pod: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    print("Deploying GuestFlow Agent to RunPod...")
    create_pod()
