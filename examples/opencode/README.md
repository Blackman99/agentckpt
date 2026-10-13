# OpenCode + agentckpt

OpenCode has no JSON hook config. It extends through JS/TS **plugins**. [`agentckpt.js`](agentckpt.js) is a small plugin for the documented [plugin API](https://opencode.ai/docs/plugins/):

```bash
pipx install git+https://github.com/Blackman99/agentckpt
cd your-repo && agentckpt init
mkdir -p .opencode/plugins && cp path/to/agentckpt/examples/opencode/agentckpt.js .opencode/plugins/
```

| Plugin hook | Fires | Snapshot message |
|-------------|-------|------------------|
| `tool.execute.before` for `edit` / `write` / `patch` / `bash` | before each edit or shell command | `opencode: before edit src/app.ts` |
| `event` → `session.idle` | when the agent finishes a turn | `opencode: turn end` |

The plugin hands agentckpt a small JSON payload as the last argument, using the same shape as Claude Code hooks, so the messages match the other agents. It uses `.quiet().nothrow()` and a `try/catch`, so a missing `agentckpt` never breaks a session, and it never throws from `tool.execute.before`. Throwing there would block the tool.

OpenCode loads files in `.opencode/plugins/` at startup. Restart it after copying.

### OpenCode V2 plugin API

If you're on the V2 plugin API (`ctx.tool.hook(...)`), the same idea is:

```ts
await ctx.tool.hook("execute.before", async (event) => {
  // event.tool, event.input
  // run: agentckpt hook --source opencode --quiet --no-stdin '<json>'
})
```

This variant is best-effort and untested. The V1 plugin above is the supported example.

### No plugins? Wrap the CLI

```bash
alias opencode='agentckpt run -m opencode -- opencode'
```

See [`../shell/`](../shell/).
