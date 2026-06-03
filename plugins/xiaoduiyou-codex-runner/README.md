# Xiaoduiyou Codex Runner

This plugin contains the local desktop runner used to keep Codex connected to Xiaoduiyou after the setup thread ends.

The Codex App plugin itself is not a daemon. The runner is installed by `scripts/install-codex-runner.sh` and runs as a macOS LaunchAgent when available.

## Install

Use the setup prompt in the root README. The prompt clones this public repo, installs the Codex platform plugin and runner plugin, writes local connection config, and starts the runner.

## Files

- `scripts/xiaoduiyou_codex_runner.py`: background runner
- `skills/xiaoduiyou-codex-runner/SKILL.md`: Codex-facing install and operations skill
