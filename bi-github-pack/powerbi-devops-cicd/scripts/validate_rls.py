#!/usr/bin/env python3
"""Ensure every dataset in workspace config declares RLS roles."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    missing = [ds["name"] for ds in cfg.get("datasets", []) if not ds.get("rls_roles")]
    if missing:
        print("RLS missing on:", ", ".join(missing)); sys.exit(1)
    for ds in cfg["datasets"]:
        print(f"OK {ds['name']}: {', '.join(ds['rls_roles'])}")
    print("RLS validation passed")


if __name__ == "__main__":
    main()
