#!/bin/bash
# Mac: double-click to start the ORB Trade Desk at http://localhost:8787
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/ and double-click this file again."
  read -r -p "Press Return to close."
  exit 1
fi
python3 desk/serve_desk.py "$@"
read -r -p "The desk stopped. Press Return to close."
