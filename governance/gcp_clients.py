#
# gcp_clients.py
#
# Contains all functions that directly interact with Google Cloud Platform services.
# OPS-authoritative, deterministic credential handling.
#

import os
import datetime

from google.cloud import secretmanager, storage, firestore
from google.oauth2 import service_account


# --------------------------------------------------
# Credential loading (AUTHORITATIVE)
# --------------------------------------------------

def _load_credentials():
    """
    Load service account credentials explicitly.

    This enforces deterministic, brokerage-grade
    credential resolution.
    """
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not cred_path:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is not set")

    if not os.path.isfile(cred_path):
        raise RuntimeError(f"Credential file not found: {cred_path}")

    return service_account.Credentials.from_service_account_file(cred_path)


# --------------------------------------------------
# Firestore
# --------------------------------------------------

def log_uncertainty_measurement(
    project_id: str,
    database_name: str,
    verdicts: dict,
    consensus: str,
    prompt: str,
):
    """
    Writes the results of an uncertainty measurement to Firestore.
    """
    print("  [PROCESS] Writing uncertainty measurement to audit log...")

    creds = _load_credentials()

    try:
        client = firestore.Client(
            project=project_id,
            database=database_name,
            credentials=creds,
        )

        doc_ref = client.collection("uncertainty_log").document()

        log_entry = {
            "timestamp_utc": datetime.datetime.utcnow(),
            "verdicts": verdicts,
            "consensus_result": consensus,
            "market_data_prompt": prompt,
        }

        doc_ref.set(log_entry)
        print(f"  [OK] Successfully wrote log entry: {doc_ref.id}")

    except Exception as e:
        print(f"  [ERROR] Failed to write to Firestore audit log: {e}")


# --------------------------------------------------
# Secret Manager
# --------------------------------------------------

def get_api_keys(project_id: str, secret_names: list) -> dict:
    """
    Retrieves the payload for a list of secrets from Secret Manager.
    """
    print("  [PROCESS] Accessing API keys from Secret Manager...")

    creds = _load_credentials()
    client = secretmanager.SecretManagerServiceClient(credentials=creds)

    keys = {}

    for name in secret_names:
        path = client.secret_version_path(project_id, name, "latest")
        response = client.access_secret_version(request={"name": path})
        payload = response.payload.data.decode("UTF-8")
        keys[name] = payload
        print(f"    - Retrieved '{name}'")

    print("  [OK] API keys retrieved.")
    return keys


# --------------------------------------------------
# Cloud Storage (Doctrine)
# --------------------------------------------------

def load_doctrine_from_gcs(project_id: str, bucket_name: str) -> dict:
    """
    Loads all doctrine files from the specified GCS bucket.
    """
    print("  [PROCESS] Loading doctrine from Cloud Storage...")

    creds = _load_credentials()
    storage_client = storage.Client(
        project=project_id,
        credentials=creds,
    )

    bucket = storage_client.bucket(bucket_name)

    doctrine = {}
    prefixes = ["LAW/", "PB/", "REF/"]

    for prefix in prefixes:
        blobs = bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            if not blob.name.endswith("/"):
                content = blob.download_as_text()
                doctrine[blob.name] = content
                print(f"    - Loaded {blob.name}")

    print("  [OK] Doctrine loading complete.")
    return doctrine
