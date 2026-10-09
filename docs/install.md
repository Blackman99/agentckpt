# Install

Python **3.9+** and `git` on `PATH`. Zero runtime Python dependencies.

=== "uvx"

    ```bash
    uvx --from git+https://github.com/Blackman99/agentckpt agentckpt --help
    uvx --from git+https://github.com/Blackman99/agentckpt agentckpt demo
    ```

=== "pipx"

    ```bash
    pipx install git+https://github.com/Blackman99/agentckpt
    agentckpt --version
    ```

=== "pip"

    ```bash
    pip install git+https://github.com/Blackman99/agentckpt
    ```

Wheels are attached to [GitHub Releases](https://github.com/Blackman99/agentckpt/releases).

## Verify

```bash
agentckpt demo
# ✅ agentckpt demo passed
```
