#!/usr/bin/env bash
# Install the 11 trader-* skills for Claude Code (personal skills folder).
set -e
cd "$(dirname "$0")"
mkdir -p "$HOME/.claude/skills"
cp -r skills/trader-* "$HOME/.claude/skills/"
echo "Installed $(ls -d skills/trader-* | wc -l | tr -d ' ') skills to $HOME/.claude/skills"
python3 --version >/dev/null 2>&1 || echo "Python 3 not found: install it from python.org (3.8 or newer)."
echo "Next: python3 desk/run_desk.py --scan skip   (creates trader/config.json; edit your limits)"
