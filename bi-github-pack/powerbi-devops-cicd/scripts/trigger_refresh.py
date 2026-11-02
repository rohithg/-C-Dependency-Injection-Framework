#!/usr/bin/env python3
"""Trigger a dataset refresh via Power BI REST API."""
from __future__ import annotations
import argparse, sys
import requests
from pbi_auth import get_access_token

API = "https://api.powerbi.com/v1.0/myorg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-id", required=True)
    ap.add_argument("--dataset-id", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    token = get_access_token(dry_run=args.dry_run)
    url = f"{API}/groups/{args.workspace_id}/datasets/{args.dataset_id}/refreshes"
    if args.dry_run:
        print(f"Dry-run OK — POST {url}")
        return
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code not in (200, 202):
        print(r.status_code, r.text); sys.exit(1)
    print("Refresh accepted:", r.status_code)


if __name__ == "__main__":
    main()
