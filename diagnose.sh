#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -x backend/.venv/bin/python ] || { echo "Run ./start.sh once first."; exit 1; }
backend/.venv/bin/python diagnose.py
