// OpenCode plugin: checkpoint the working tree with agentckpt.
// Copy to .opencode/plugins/agentckpt.js (project) or ~/.config/opencode/plugins/agentckpt.js (global).
// Requires `agentckpt` on PATH and `agentckpt init` in the project (otherwise every call is a no-op).

const SNAP_BEFORE = new Set(["edit", "write", "patch", "apply_patch", "multiedit", "bash"])

export const Agentckpt = async ({ $, directory }) => {
  const snap = async (payload) => {
    // Pass the payload as the last argv (Bun's $ escapes it as one argument). Never throw.
    const json = JSON.stringify({ cwd: directory, ...payload })
    try {
      await $`agentckpt hook --source opencode --quiet --no-stdin ${json}`.quiet().nothrow()
    } catch {
      // agentckpt missing or failed: never break the session
    }
  }

  return {
    "tool.execute.before": async (input, output) => {
      if (!SNAP_BEFORE.has(input.tool)) return
      const args = output?.args ?? {}
      await snap({
        hook_event_name: "PreToolUse",
        tool_name: input.tool,
        tool_input: { filePath: args.filePath, command: args.command },
      })
    },
    event: async ({ event }) => {
      if (event.type === "session.idle") await snap({ hook_event_name: "Stop" })
    },
  }
}
