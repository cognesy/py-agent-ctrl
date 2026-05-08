# Go orchestrator foundation notes

Date: 2026-03-18

## Purpose

Translate the `tmux` experiment into implementation guidance for a future Go-based orchestrator that supervises multiple Codex TUI instances.

## Recommendation

Implement the first version in Go as a thin, explicit session manager around `tmux`, not as a generic terminal emulator.

The core design should be:
- one `tmux` session per child agent
- a small Go state machine per child
- polling via `tmux capture-pane`
- command dispatch via `tmux send-keys`
- optional `tmux pipe-pane` log capture for diagnostics

## Why Go fits

Go is a good fit because the problem is mostly:
- process orchestration
- timeouts and retries
- concurrent supervision of many children
- lightweight parsing and event handling
- durable logging and state persistence

This is simpler and safer than embedding a full terminal parser unless later evidence proves it necessary.

## Architecture sketch

### Components

1. Session manager
- creates and destroys `tmux` sessions
- assigns session names
- tracks working directories and launch commands

2. Agent controller
- owns one child agent lifecycle
- submits prompts
- polls snapshots
- decides whether the child is idle, working, or unhealthy

3. Pane parser
- normalizes `capture-pane` text
- strips obvious UI noise
- extracts prompt/response candidates
- detects state markers such as working/idle

4. Scheduler
- decides which child receives which task
- enforces concurrency limits
- handles retries and task reassignment

5. Transcript store
- persists prompts, responses, raw snapshots, and errors
- supports replay/debugging after failures

6. Diagnostics layer
- optional `pipe-pane` archival
- structured logs for child lifecycle and command execution

## State model

Each child agent should expose a narrow state machine:

- `Starting`
- `Idle`
- `Submitting`
- `Working`
- `Completed`
- `Interrupted`
- `Stuck`
- `Dead`

Suggested transitions:
- `Starting` -> `Idle` when the TUI reaches recognizable ready state
- `Idle` -> `Submitting` when the master sends a prompt
- `Submitting` -> `Working` when pane output shows activity
- `Working` -> `Completed` when a response is observed and the TUI returns to idle
- any state -> `Stuck` on timeout without progress
- any state -> `Dead` if the pane process exits

## Command execution strategy

Do not shell out with ad hoc command strings scattered through the codebase.

Wrap `tmux` invocations behind typed Go methods such as:

```go
type Tmux interface {
    NewSession(ctx context.Context, session string, cmd string) error
    CapturePane(ctx context.Context, target string, startLine int) (string, error)
    SendLiteral(ctx context.Context, target string, text string) error
    SendEnter(ctx context.Context, target string) error
    ListPane(ctx context.Context, target string) (PaneInfo, error)
    PipePane(ctx context.Context, target string, outputPath string) error
    KillSession(ctx context.Context, session string) error
}
```

This makes it easier to:
- test orchestration logic
- replace command details later
- centralize escaping and timeout behavior

## Parsing strategy

Prefer a conservative parser.

The first implementation should not attempt a full semantic understanding of the TUI. It should only detect:
- whether the child appears idle
- whether the child is actively generating
- the latest visible prompt
- the latest visible assistant response

Good enough beats clever here. Use heuristics that can be refined later.

## Reliability guidance

### Use snapshots as source of truth

`pipe-pane` is useful, but `capture-pane` should drive state decisions because:
- it is easier to sanitize
- it reflects the visible pane state
- it is less noisy than raw terminal stream data

### Separate text input from submit

The experiment showed that:
- `send literal text`
- then `send Enter`

is safer than batching everything into one injected keystroke sequence.

### Build timeout classes

Use distinct timeouts for:
- startup timeout
- submit acknowledgment timeout
- generation timeout
- idle stabilization timeout

This will make recovery logic less ambiguous.

### Design for restartability

The orchestrator should be able to:
- recreate a dead child session
- rehydrate task ownership from persisted state
- mark uncertain tasks as needing operator review

## Suggested data model

```go
type AgentID string

type AgentState string

const (
    AgentStarting    AgentState = "starting"
    AgentIdle        AgentState = "idle"
    AgentSubmitting  AgentState = "submitting"
    AgentWorking     AgentState = "working"
    AgentCompleted   AgentState = "completed"
    AgentInterrupted AgentState = "interrupted"
    AgentStuck       AgentState = "stuck"
    AgentDead        AgentState = "dead"
)

type Agent struct {
    ID         AgentID
    Session    string
    PaneTarget string
    WorkDir    string
    State      AgentState
    LastPrompt string
    LastReply  string
    LastSeen   time.Time
    StartedAt  time.Time
}
```

## First implementation milestone

The first useful milestone should be narrow:

1. create `N` child Codex sessions
2. submit simple prompts
3. wait for completion using pane polling
4. collect final visible replies
5. write transcripts and basic health logs

Do not start with:
- dynamic pane layouts
- interactive dashboards
- complex task routing
- speculative multiturn recovery

Those can come after the basic control loop proves stable over many runs.

## Open issues to validate next

1. How stable are the visible idle/working markers across Codex CLI releases?
2. What is the safest way to extract the latest assistant response from pane history?
3. How well does this hold up with many concurrent child sessions?
4. Does `codex exec` or another non-TUI mode cover some orchestration cases more safely than driving the TUI?
5. What retry policy is acceptable when the pane content becomes ambiguous?

## Bottom line

A Go implementation should treat `tmux` as a transport and Codex TUI as a loosely observable state machine.

That is a workable foundation. The engineering priority is not sophistication; it is determinism, bounded failure modes, and good diagnostics.
