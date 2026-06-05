#!/usr/bin/env python3
"""Minimal JSON stub for local ghost-optic LLM smoke tests."""

import json
import sys


def main() -> None:
    _ = sys.stdin.read()
    print(json.dumps({"inject_ids": ["D00"], "reason": "stub"}))


if __name__ == "__main__":
    main()
