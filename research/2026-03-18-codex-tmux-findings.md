# Codex over tmux: empirical findings

Date: 2026-03-18
Environment:
- Host: macOS
- `codex-cli`: `0.115.0`
- `tmux`: `3.6a`
- Shell used for testing: `zsh`

## Goal

Validate whether a "master" process can supervise and drive multiple subordinate Codex TUI instances through `tmux`, using terminal-level observation and injected input rather than a dedicated API.

## Summary

This is feasible.

The tested control loop worked:
- start a Codex TUI in its own detached `tmux` session
- observe pane state with `tmux capture-pane`
- inject prompts with `tmux send-keys`
- optionally stream pane output with `tmux pipe-pane`

This is good enough to serve as the foundation of an orchestrator, but it remains terminal automation, not protocol-level automation. The implementation must treat the child agent as a stateful TUI with imperfect observability.

## What was tested

### 1. Tool availability

Confirmed locally:
- `codex` was already installed at `/opt/homebrew/bin/codex`
- `tmux` was not installed initially
- `tmux` was installed successfully via Homebrew

Observed versions:
- `codex-cli 0.115.0`
- `tmux 3.6a`

### 2. Launching Codex under tmux

This launch pattern worked:

```sh
tmux new-session -d -s agent1 \
  'cd /Users/ddebowczyk && codex --dangerously-bypass-approvals-and-sandbox --no-alt-screen'
```

Also tested:

```sh
tmux new-session -d -s agent1 \
  'cd /Users/ddebowczyk && codex --dangerously-bypass-approvals-and-sandbox --no-alt-screen "Reply with exactly PONG and nothing else."'
```

Both launched successfully inside detached sessions.

### 3. Reading the subordinate TUI

This worked:

```sh
tmux capture-pane -p -t agent1:0.0 -S -200
```

The pane buffer contained readable Codex UI content, including:
- header and model status
- current prompt
- prior assistant response

Important detail:
- `--no-alt-screen` materially improved capture usability
- without it, terminal scraping is expected to be less stable and less readable

### 4. Sending prompts to the subordinate TUI

This worked reliably:

```sh
tmux send-keys -t agent1:0.0 -l 'Reply with exactly PING and nothing else.'
tmux send-keys -t agent1:0.0 Enter
```

Observed result:
- Codex displayed the injected prompt
- Codex produced the requested answer
- the conversation continued to the next turn normally

The following prompt/response sequence was verified:
- `Reply with exactly PONG and nothing else.` -> `PONG`
- `Reply with exactly PING and nothing else.` -> `PING`
- `Reply with exactly PLOP and nothing else.` -> `PLOP`

### 5. Batched submit behavior

An earlier variant was less reliable:

```sh
tmux send-keys -t agent1:0.0 C-u 'Reply with exactly PING and nothing else.' C-m
```

The prompt text appeared, but the response did not reliably execute.

The safer approach is:
- send literal text first
- send `Enter` in a separate `tmux send-keys` call

This should be treated as the default orchestration pattern.

### 6. Live streaming pane output

This worked:

```sh
tmux pipe-pane -o -t agent1:0.0 'cat >> /tmp/agent1.log'
```

Result:
- output was streamed continuously to a file
- the stream included ANSI escape sequences and screen-control bytes

Implication:
- live stream is useful for audit/debugging
- parsing should either strip ANSI sequences or prefer `capture-pane` snapshots for state extraction

## Operational observations

### Prompt submission state

The Codex TUI accepted follow-up turns after the initial prompt completed. This is critical: the child session did not need to be relaunched for each request.

### Pane process identity

`tmux list-panes` correctly reported the pane PID and current command, which is useful for health checks:

```sh
tmux list-panes -t agent1 -F '#{session_name} #{window_index}.#{pane_index} pid=#{pane_pid} cmd=#{pane_current_command} active=#{pane_active}'
```

### Read model

There are two usable observation modes:

1. Snapshot mode with `capture-pane`
2. Streaming mode with `pipe-pane`

Snapshot mode is cleaner for orchestration logic.
Streaming mode is better for debugging, recording, and postmortems.

## Constraints and risks

### 1. This is TUI automation, not an API

The orchestrator does not receive structured events. It sees terminal state. That means:
- text parsing can break if the UI changes
- timing matters
- transient states must be tolerated

### 2. Full-screen terminal behavior is noisy

Even with `--no-alt-screen`, the UI is still a terminal app. The orchestrator should expect:
- redraws
- spinner/status updates
- line wrapping
- ANSI control sequences in streamed output

### 3. Input timing matters

Prompt text and submit should be sent as distinct operations. Treat prompt dispatch as a small state machine, not one shell command.

### 4. Recovery must be built in

The master process should assume child sessions can become:
- busy
- interrupted
- stuck
- detached from the expected screen state

This implies the need for health checks and restart/resume logic.

## Recommended baseline control contract

The orchestrator should interact with each child session using a minimal contract:

1. Start child in dedicated `tmux` session
2. Wait for recognizable idle prompt state
3. Send prompt text literally
4. Send `Enter`
5. Poll `capture-pane`
6. Detect transition from "working" to idle state
7. Extract the assistant response from pane history
8. Persist transcript and health metadata

## Practical command set

Suggested primitive commands:

```sh
# launch
tmux new-session -d -s agent1 'cd /workdir && codex --dangerously-bypass-approvals-and-sandbox --no-alt-screen'

# snapshot
tmux capture-pane -p -t agent1:0.0 -S -300

# send text
tmux send-keys -t agent1:0.0 -l 'Do X and only report Y.'

# submit
tmux send-keys -t agent1:0.0 Enter

# inspect process/health
tmux list-panes -t agent1 -F '#{pane_pid} #{pane_current_command} #{pane_dead}'

# stream to log
tmux pipe-pane -o -t agent1:0.0 'cat >> /tmp/agent1.log'

# terminate
tmux kill-session -t agent1
```

## Bottom line

The tmux-driven approach is viable for a multi-agent Codex orchestrator.

It should be built with the assumption that:
- observation is textual and approximate
- control is keystroke-based
- robust state detection matters more than UI elegance

Given those constraints, the experiment supports moving forward with an implementation.
