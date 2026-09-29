#!/usr/bin/env python3
"""Diff dataset/RLS config between two workspace JSON files (dev vs prod)."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path


def index(cfg):
    return {ds["name"]: set(ds.get("rls_roles", [])) for ds in cfg.get("datasets", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--left", required=True)
    ap.add_argument("--right", required=True)
    args = ap.parse_args()
    left = index(json.loads(Path(args.left).read_text()))
    right = index(json.loads(Path(args.right).read_text()))
    names = sorted(set(left) | set(right))
    drift = False
    for n in names:
        if n not in left:
            print(f"ONLY_RIGHT {n}"); drift = True
        elif n not in right:
            print(f"ONLY_LEFT {n}"); drift = True
        elif left[n] != right[n]:
            print(f"RLS_DRIFT {n}: left={sorted(left[n])} right={sorted(right[n])}")
            drift = True
        else:
            print(f"OK {n}")
    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    main()
