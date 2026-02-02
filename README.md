# claude-pipe helper tool

Pipe prompts to claude cli via tmux and get clean text back.

## Why not `claude -p`?

`claude -p` (pipe/headless mode) requires paid API tokens. If you already pay for **Claude Pro** (or Max, or Team), that's paying twice for the same model. claude-pipe drives the interactive CLI through tmux instead — same results, zero extra cost.

## Use case examples

A common use case involves sending unstructured data (like log files or code snippets) to Claude via `claude-pipe`, along with a prompt to process it into a specific structured format (e.g., JSON). This allows for easy integration with other scripts or tools that can then parse and utilize the structured output for further automation or analysis.

## Install

```
uv tool install /path/to/claude-pipe
```

### Using make

To install dependencies, run:
```sh
make install
```

To install the script as a CLI tool, run:
```sh
make install-cli
```

By default, this will install the script to `/usr/local/bin`. You can customize the installation directory by passing the `INSTALL_DIR` variable:
```sh
make install-cli INSTALL_DIR=~/.local/bin
```
Note that the default installation requires `sudo` to write to `/usr/local/bin`.

Or run directly from the project:

```
uv run python main.py "your prompt"
```

## Usage

```sh
# Pass prompt as arguments
claude-pipe "explain this error"

# Pipe from stdin
echo "what does this do?" | claude-pipe

# Chain with other tools
cat traceback.txt | claude-pipe "summarize this error" > summary.txt

# Verbose mode (show status on stderr)
claude-pipe -v "list all files"
```

## How it works

1. Connects to tmux session `0` (creates it if needed)
2. Starts the AI agent if not already running
3. Sends `/clear` to reset conversation context to reduce token cost
4. Sends the prompt and waits for completion (end marker + idle detection)
5. Strips CLI chrome (bullets, decoration) and prints clean text to stdout

stderr gets errors only (or status messages with `-v`). stdout is always clean output, safe to pipe.

## Configuration

Edit constants at the top of `main.py`:

| Variable | Default | Purpose |
|---|---|---|
| `SESSION_NAME` | `"0"` | tmux session to use |
| `AGENT_CMD` | `"claude"` | CLI command to launch |
| `IDLE_TIMEOUT_S` | `5.0` | Seconds of silence before done |
| `MAX_WAIT_S` | `300` | Hard timeout |

## Other tools
The following two tools do not need a wrapper:
- Gemini: `echo 2+2|gemini` works
- copilot: `echo "say hello in 5 lines" | copilot 2>&1 | python3 -c "import sys; print(sys.stdin.read().split('\n\nTotal usage est:')[0])"`

## Requirements

- Python 3.13+
- tmux
- An AI CLI tool (currently: `claude`)
- [uv](https://docs.astral.sh/uv/)
