#!/usr/bin/env python3
"""Validate + (optionally) deploy workspace config to Power BI."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import requests
from pbi_auth import get_access_token

API = "https://api.powerbi.com/v1.0/myorg"


def validate_config(cfg: dict) -> list[str]:
    errors = []
    if not cfg.get("workspace_name"):
        errors.append("workspace_name required")
    for ds in cfg.get("datasets", []):
        if not ds.get("rls_roles"):
            errors.append(f"{ds.get('name')}: rls_roles empty")
        if not ds.get("id"):
            errors.append(f"{ds.get('name')}: dataset id missing")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    errors = validate_config(cfg)
    if errors:
        print("CONFIG ERRORS:"); [print(" -", e) for e in errors]; sys.exit(1)
    token = get_access_token(dry_run=args.dry_run)
    print(f"workspace={cfg['workspace_name']} datasets={len(cfg['datasets'])} dry_run={args.dry_run}")
    if args.dry_run:
        print("Dry-run OK — would PUT workspace description + verify datasets via REST")
        return
    headers = {"Authorization": f"Bearer {token}"}
    # Example: list workspaces (real deploy would create/update)
    r = requests.get(f"{API}/groups", headers=headers, timeout=30)
    r.raise_for_status()
    names = [g["name"] for g in r.json().get("value", [])]
    print("accessible workspaces:", ", ".join(names[:20]))


if __name__ == "__main__":
    main()
