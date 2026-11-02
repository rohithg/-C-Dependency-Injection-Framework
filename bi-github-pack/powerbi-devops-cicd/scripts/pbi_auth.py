"""Azure AD client-credentials token for Power BI REST API."""
from __future__ import annotations
import os
import requests

SCOPE = "https://analysis.windows.net/powerbi/api/.default"


def get_access_token(dry_run: bool = False) -> str:
    if dry_run:
        return "DRY_RUN_TOKEN"
    tenant = os.environ["PBI_TENANT_ID"]
    client_id = os.environ["PBI_CLIENT_ID"]
    secret = os.environ["PBI_CLIENT_SECRET"]
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": secret,
            "scope": SCOPE,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]
