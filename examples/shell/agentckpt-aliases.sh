# Source from ~/.bashrc or ~/.zshrc:   . /path/to/agentckpt-aliases.sh
#
# Snap before and after a whole agent session, for agents without hooks
# (Aider, Cursor CLI, Amp, …) or as a belt-and-braces layer on top of hooks.
# `agentckpt run` resolves the real binary on PATH, so wrapping a command
# with a function of the same name doesn't recurse.

aider()        { agentckpt run -m aider        -- aider        "$@"; }
cursor-agent() { agentckpt run -m cursor-agent -- cursor-agent "$@"; }
opencode()     { agentckpt run -m opencode     -- opencode     "$@"; }

# Generic: `ackpt <any agent> [args...]`
ackpt() { agentckpt run -m "$1" -- "$@"; }
