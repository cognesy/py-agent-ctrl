# NanoClaw Architecture Notes

This note documents how the local `nanoclaw` checkout is built and how it
operates at runtime. The goal is not product-level marketing summary. The goal
is to understand the concrete control flow and the engineering design choices:

- how inbound messages are ingested and queued
- how work is delegated to containerized Claude Agent SDK sessions
- how host files are exposed to containers
- how NanoClaw talks to external services
- how recurring and one-shot tasks are scheduled and executed

The implementation inspected here is the local repo at
`~/projects/nanoclaw`.

## Executive Summary

NanoClaw is a single-host, single-process orchestrator built around five core
ideas:

1. Channels ingest messages from external systems and write them into a local
   SQLite database.
2. A polling loop reads newly stored messages from SQLite and decides which
   group should be processed.
3. An in-memory per-group queue controls concurrency and container lifecycle.
4. Actual agent execution happens inside Docker containers running Anthropic's
   Claude Agent SDK.
5. Containers communicate back to the host through bind-mounted filesystem IPC,
   not through RPC over sockets.

This is important: NanoClaw does not use a durable external message broker, a
job queue service, Kubernetes, or a multi-process worker fleet. The architecture
is intentionally small:

`channels -> SQLite -> polling/orchestration loop -> in-memory group queue -> Docker container -> Claude Agent SDK -> filesystem IPC -> outbound channel`

It is closer to a "local orchestrator with a sandboxed agent runtime" than to a
distributed agent platform.

## High-Level Runtime Topology

At runtime, NanoClaw consists of:

- one long-lived host Node.js process
- zero or more connected channel adapters
- one SQLite database on local disk
- one local credential proxy on the host
- zero or more running agent containers
- one reusable container image, typically `nanoclaw-agent:latest`

The host process is responsible for:

- connecting to channels
- storing inbound state in SQLite
- deciding what work is pending
- limiting concurrency across groups
- launching and reaping containers
- authorizing and applying container-originated actions
- sending outbound messages
- scheduling recurring tasks

The containers are responsible for:

- running Claude Agent SDK queries
- maintaining agent session continuity inside a group context
- reading mounted workspace files
- invoking local tools and MCP servers
- writing host requests into IPC directories

## Core Components

### 1. Host Orchestrator

The main process is implemented in `src/index.ts`. It initializes:

- Docker availability checks
- SQLite schema and persisted state
- channel connections
- the credential proxy
- the scheduler loop
- the IPC watcher
- the main polling loop for inbound messages

This is a centralized controller. There is no separate worker process for
message handling and no standalone scheduler service.

### 2. Channels

Channels are pluggable adapters registered through `src/channels/registry.ts`
and loaded by `src/channels/index.ts`.

Examples in this checkout:

- WhatsApp via Baileys
- Telegram
- Gmail

Channel responsibilities:

- connect to the external messaging/email service
- translate service-specific events into NanoClaw `NewMessage` records
- emit chat metadata for discovery
- send outbound messages back to the original service

Different channels ingest differently:

- WhatsApp is event-driven. It listens to Baileys socket events and forwards
  inbound messages immediately.
- Gmail is polling-based. It periodically queries unread messages, converts
  them into messages for the NanoClaw main group, and marks them as read.

### 3. SQLite Persistence

NanoClaw uses a local SQLite database via `better-sqlite3`. The database
contains:

- `chats`
- `messages`
- `scheduled_tasks`
- `task_run_logs`
- `router_state`
- `sessions`
- `registered_groups`

This database is not just storage. It is part of the queueing model.

Important persistence roles:

- `messages` is the durable inbound message buffer
- `router_state.last_timestamp` tracks how far the top-level polling loop has
  scanned
- `router_state.last_agent_timestamp` tracks how far each group has been handed
  to an agent
- `sessions` maps each group folder to its Claude session id
- `scheduled_tasks` is the durable task schedule registry

### 4. Group Queue

`src/group-queue.ts` implements the in-memory work queue. This is the key
component that decides whether a group already has an active container, whether
new input should be piped into that container, and when a new container should
be started.

Important properties of the queue:

- state is maintained per group JID
- each group can have at most one active execution path at a time
- there is a global concurrent container cap
- pending work is tracked separately for messages and scheduled tasks
- scheduled tasks are prioritized over message work during draining
- retries with exponential backoff apply to message processing failures

This is not a durable job queue on its own. It sits on top of SQLite. If the
process dies, pending messages are recovered from the database, but the in-memory
queue itself is lost.

### 5. Container Runner

`src/container-runner.ts` is the boundary between the host orchestrator and the
agent sandbox. It:

- builds the list of host bind mounts
- constructs `docker run` arguments
- injects environment variables for proxy-based auth
- spawns the container process
- streams stdout/stderr
- parses structured output markers
- writes diagnostic logs for each run

Each container run gets a unique name like:

`nanoclaw-<group-folder>-<timestamp>`

So there is one host process and many ephemeral containers over time. There is
not one permanent sandbox container for the whole system.

### 6. Container-Side Agent Runner

Inside the container, `container/agent-runner/src/index.ts` runs the actual
Claude Agent SDK loop. This code:

- reads a JSON input object from stdin
- calls `query(...)` from `@anthropic-ai/claude-agent-sdk`
- exposes a NanoClaw MCP server to the agent
- streams outputs back to the host via stdout markers
- stays alive to accept follow-up IPC messages
- exits when the host writes a `_close` sentinel

This is the core "agent execution runtime". Docker provides isolation, but the
agent semantics come from Anthropic's SDK.

### 7. Credential Proxy

`src/credential-proxy.ts` starts a host-local HTTP proxy, typically on
`127.0.0.1:3001`.

Its job is to prevent real Anthropic credentials from entering the container.

Instead of the container talking directly to Anthropic:

- the container sends API traffic to `http://host.docker.internal:3001`
- the proxy injects the real auth headers
- the proxy forwards the request to the upstream Anthropic-compatible endpoint

This is how NanoClaw keeps secrets on the host while still allowing the
containerized Claude runtime to function.

### 8. IPC Watcher

`src/ipc.ts` scans per-group IPC directories under `data/ipc/` and applies
requests emitted by containers.

This is the host-side control plane for container-originated actions such as:

- send a message now
- schedule a task
- pause/resume/cancel/update a task
- register a group
- refresh group metadata

Authorization is enforced here based on the group identity implied by the IPC
directory, not by trusting container-supplied claims.

### 9. Scheduler

`src/task-scheduler.ts` is a periodic loop that:

- queries SQLite for due tasks
- enqueues them into `GroupQueue`
- runs them in containers
- stores execution logs and next-run metadata

Scheduled tasks are therefore not a special execution engine. They reuse the
same container runtime as normal message handling.

## State Model

NanoClaw has two state layers.

### Durable State

Durable state lives in SQLite and on disk:

- messages
- registered groups
- task schedule definitions
- task run logs
- per-group Claude session ids
- per-group files in `groups/`
- per-group `.claude` session/config state under `data/sessions/`
- IPC files and snapshots under `data/ipc/`

### In-Memory State

Transient in-memory state lives in the host process:

- connected channels
- `registeredGroups` cache
- `sessions` cache
- `lastTimestamp`
- `lastAgentTimestamp`
- active `GroupQueue` state

This design keeps durable recovery simple, but it also means NanoClaw is not a
multi-host system. The host process is the authority.

## Message Ingestion Path

### Step 1: Channel receives external input

A channel adapter receives new input from the outside world.

Examples:

- WhatsApp receives a `messages.upsert` event from Baileys.
- Gmail polling finds a new unread email and converts it into a message for the
  main group.

Channels always emit chat metadata. Full message content is only forwarded to
NanoClaw if the target chat is a registered group.

This is an important storage optimization:

- all known chats can exist in `chats`
- only registered groups get full message history stored in `messages`

### Step 2: Shared channel callbacks persist the input

Every channel is created with common callbacks from `src/index.ts`.

The shared `onMessage` callback:

- optionally intercepts `/remote-control` commands
- optionally drops disallowed senders before storage
- writes the message row into SQLite

The shared `onChatMetadata` callback updates the `chats` table.

At this point the message is not yet being processed by Claude. It is only
persisted.

### Step 3: Top-level polling loop reads new rows from SQLite

`startMessageLoop()` in `src/index.ts` polls SQLite every `POLL_INTERVAL`
(2 seconds by default) and calls `getNewMessages(...)`.

The polling loop:

- fetches newly stored messages for registered groups
- advances the global scan cursor `lastTimestamp`
- groups messages by `chat_jid`
- decides whether each group should trigger agent execution

Important implication:

NanoClaw does not drive agent execution directly from channel callbacks.
Channels only store events. The message loop is a second-stage dispatcher that
reads from SQLite.

### Step 4: Trigger gating and context expansion

For non-main groups, NanoClaw usually requires a trigger word such as
`@Andy`. If a new batch does not contain a valid trigger, the batch is left in
SQLite and not sent to the agent yet.

When a valid trigger appears, NanoClaw loads all messages since the group's
`lastAgentTimestamp`, not just the latest trigger message batch.

That means:

- non-trigger messages can accumulate as latent context
- the next trigger flushes the whole unseen conversation window into the agent

This is a deliberate context-building behavior, not an accident.

## How Messages Are Actually Enqueued

The real queueing model is subtle:

- durable buffering happens in SQLite
- active execution control happens in `GroupQueue`

There is no separate broker like Redis, RabbitMQ, SQS, or Kafka.

### If a container is already active for the group

The host tries `queue.sendMessage(chatJid, formattedPrompt)`.

If that succeeds:

- the host writes a JSON file into `data/ipc/<group>/input/`
- the already-running container picks it up
- the host updates `lastAgentTimestamp`
- no new container is spawned

So NanoClaw can keep a group's container "warm" and stream additional user
messages into the same Claude session.

### If no container is active for the group

The host calls `queue.enqueueMessageCheck(chatJid)`.

That marks the group as needing work and either:

- starts processing immediately if capacity exists
- or records `pendingMessages` and waits for a concurrency slot

### Why the queue is per-group

The queue is designed around serialized group execution:

- one group should not have multiple simultaneous agent runs
- tasks and messages within a group must be ordered
- a running group container can accept follow-up work via IPC

This design is much closer to "actor per conversation group" than to "independent
task per message."

## End-to-End Message Execution Path

When a group is selected for processing:

1. `GroupQueue` calls `processGroupMessages(chatJid)`.
2. The host loads all unseen messages since `lastAgentTimestamp`.
3. It formats them into XML-like `<message ...>` records using `router.ts`.
4. It advances the per-group cursor before execution, with rollback on failure.
5. It starts typing indicators on the owning channel if supported.
6. It calls `runAgent(...)`.
7. `runAgent(...)` writes task and group snapshots for the container.
8. `runContainerAgent(...)` launches Docker with the correct mounts and env.
9. The container-side runner calls the Claude Agent SDK.
10. Results stream back via stdout markers.
11. The host forwards non-internal output to the originating channel.
12. The container remains alive for follow-up IPC input until idle close.

Important detail:

If the agent already produced output to the user and then errors, NanoClaw does
not roll back the cursor, because retrying would duplicate the visible response.

## Container Delegation Model

The delegation boundary is implemented directly with `docker run`.

### Host-side mechanics

For each agent execution, the host:

- constructs a container name
- assembles bind mounts
- sets the timezone
- points `ANTHROPIC_BASE_URL` at the local credential proxy
- injects placeholder auth values, not real secrets
- optionally maps host uid/gid into the container for file permission
  compatibility
- spawns the container process with stdin/stdout/stderr pipes

The host writes a JSON object to container stdin containing:

- prompt
- session id if one exists
- group folder
- chat JID
- whether this is the main group
- whether this is a scheduled task

### Container-side mechanics

The image entrypoint:

- recompiles the mounted container-side source into `/tmp/dist`
- reads stdin into `/tmp/input.json`
- runs `node /tmp/dist/index.js < /tmp/input.json`

Inside that process, the agent runner:

- builds the initial prompt
- drains any pending IPC messages into the prompt
- calls `query(...)` from the Claude Agent SDK
- streams results to stdout with explicit boundary markers
- remembers the resulting session id
- waits for more IPC messages
- loops until the host writes `_close`

### This is not one-container-per-message

NanoClaw often reuses a live container for one group across several user
messages.

The lifecycle is:

- first message starts a container
- follow-up messages arrive through filesystem IPC
- idle timeout or explicit close ends the container

Scheduled task containers are treated more like single-turn runs and are closed
promptly after producing output.

## Container Tooling and Agent Capabilities

The agent runner grants Claude a curated tool surface via the SDK. The allowed
tool list includes:

- Bash
- Read / Write / Edit / Glob / Grep
- WebSearch / WebFetch
- Task / TaskOutput / TaskStop
- TeamCreate / TeamDelete / SendMessage
- TodoWrite / ToolSearch / Skill / NotebookEdit
- NanoClaw MCP tools
- Gmail MCP tools

It also enables:

- Claude agent teams / subagents
- loading `CLAUDE.md` from additional directories
- persistent per-group `.claude` state

So the agent is not just a pure text completion. It is a tool-using Claude Code
style runtime inside a container.

## Host Filesystem Access Model

This is one of the most important parts of the design.

NanoClaw uses bind mounts to define what the container can see.

### Main group mounts

The main group gets:

- the project root mounted read-only at `/workspace/project`
- its own group folder mounted read-write at `/workspace/group`
- its own `.claude` directory mounted read-write at `/home/node/.claude`
- its own IPC directory mounted read-write at `/workspace/ipc`
- a writable copy of agent-runner source mounted at `/app/src`

Additionally:

- if `.env` exists in the project root, it is shadowed by mounting `/dev/null`
  over `/workspace/project/.env`

That means the main group can inspect the project code, but cannot directly read
the host `.env` secrets through the mounted project tree.

### Non-main group mounts

Non-main groups get a smaller surface:

- their own group folder at `/workspace/group`
- the global memory directory at `/workspace/global` read-only, if present
- their own `.claude` directory
- their own IPC directory
- their own writable copy of the agent-runner source

Non-main groups do not automatically get the whole NanoClaw project root.

### Additional host mounts

Groups can request `containerConfig.additionalMounts`, but those mounts are
validated against an allowlist stored outside the project at:

`~/.config/nanoclaw/mount-allowlist.json`

Validation rules include:

- the host path must exist
- the path must be under an allowed root
- blocked patterns like `.ssh`, `.gnupg`, `.aws`, `.env`, private keys, and
  similar sensitive names are rejected
- container mount targets are forced under `/workspace/extra/...`
- non-main groups can be forced to read-only even if read-write was requested

This is a meaningful defense boundary because the allowlist file itself is not
mounted into the container.

### Per-group writable state

Each group has isolated writable state on the host:

- `groups/<folder>/` for the group's working files
- `data/sessions/<folder>/.claude/` for Claude session/config state
- `data/ipc/<folder>/` for control-plane exchange
- `data/sessions/<folder>/agent-runner-src/` for a writable copy of the
  container-side runner source

The writable `agent-runner-src` mount is unusual and important. It means the
agent can customize the container-side runtime for that group without mutating
the shared source tree for other groups.

## Secrets Model

NanoClaw is careful not to put sensitive API tokens directly into child-process
environment or container mounts.

### `.env` handling

`src/env.ts` reads selected keys from `.env` on demand and returns them to the
caller without globally exporting them into `process.env`.

This reduces accidental leakage into child processes.

### Anthropic credentials

The container never receives the real:

- `ANTHROPIC_API_KEY`
- `CLAUDE_CODE_OAUTH_TOKEN`
- `ANTHROPIC_AUTH_TOKEN`

Instead:

- the container receives placeholder values
- all Anthropic traffic is sent to the host-local credential proxy
- the proxy injects the real auth information

This is a strong design choice and one of the cleaner parts of the system.

## IPC Control Plane

NanoClaw uses filesystem IPC rather than a socket server or direct callback
bridge.

Each group gets a namespace like:

- `data/ipc/<group>/messages/`
- `data/ipc/<group>/tasks/`
- `data/ipc/<group>/input/`

### Container -> host path

The container-side NanoClaw MCP server writes JSON files into:

- `messages/` to request outbound user-visible messages
- `tasks/` to request task and admin operations

The host-side IPC watcher scans those directories and applies the requests.

### Host -> container path

The host writes JSON files into:

- `input/` for follow-up prompt content
- `_close` as a sentinel to ask the container to exit

This gives NanoClaw a simple, inspectable bridge that works across subagents
because it is filesystem-based.

### Authorization model

The host does not trust arbitrary fields in the IPC payload.

Instead, it derives authority from the source IPC directory:

- main-group IPC can act across groups
- non-main-group IPC can usually only act on its own chat/task space

This authorization is enforced in `src/ipc.ts`.

## MCP Tools Exposed To The Agent

The container-side NanoClaw MCP server exposes host-integrated tools such as:

- `send_message`
- `schedule_task`
- `list_tasks`
- `pause_task`
- `resume_task`
- `cancel_task`
- `update_task`
- `register_group`

These are not executed directly inside the container. They write IPC files for
the host to evaluate and apply.

This split matters:

- tool invocation is initiated by Claude inside the container
- authority remains with the host

## External Service Interactions

NanoClaw interacts with external services in several distinct ways.

### Messaging channels

Channels connect directly to messaging/email providers.

Examples from this checkout:

- WhatsApp via Baileys
- Gmail via Google APIs and OAuth2
- Telegram support is also present in the source tree

These channel adapters are where service-specific auth, polling, and transport
details live.

### Anthropic or Anthropic-compatible model endpoint

The actual agent runtime calls Anthropic-compatible APIs from inside the
container, but the traffic is proxied through the host credential proxy.

The README indicates NanoClaw can be pointed at compatible non-Anthropic
providers by setting:

- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_AUTH_TOKEN`

So the agent runtime is Claude-Agent-SDK-centric, but not strictly tied to the
hosted Anthropic endpoint.

### Gmail MCP inside the container

The agent runner configures a Gmail MCP server using:

`npx -y @gongrzhe/server-gmail-autoauth-mcp`

The corresponding host credentials directory `~/.gmail-mcp` is mounted into the
container if it exists. This allows Claude to use Gmail tools from inside the
container without NanoClaw itself becoming the Gmail execution engine.

### Browser automation inside the container

The Docker image installs Chromium and `agent-browser`. That implies web tasks
and browser automation are intended to happen inside the sandbox, not on the
host.

## Main Group vs Regular Groups

NanoClaw has a privileged concept of the "main group".

The main group is special because it can:

- process messages without trigger gating
- see all available groups
- see all tasks
- register new groups
- refresh group metadata
- schedule tasks for other groups
- access the project root read-only

Regular groups are more restricted:

- they usually require a trigger
- they operate within their own chat and folder scope
- they only manage their own tasks
- they do not get global visibility or project-root access by default

This is effectively a built-in control-plane vs data-plane split.

## Scheduling Architecture

Scheduling in NanoClaw is SQLite-backed and host-driven.

### Task creation

Tasks are usually created by the agent through the NanoClaw MCP tool
`schedule_task`.

The flow is:

1. Claude calls `schedule_task` inside the container.
2. The MCP server validates the schedule format locally.
3. The MCP server writes a task request JSON file into the group's IPC
   `tasks/` directory.
4. The host IPC watcher authorizes the action and persists the task in SQLite.

Task fields include:

- task id
- owning group folder
- target chat JID
- prompt
- schedule type: `cron`, `interval`, or `once`
- schedule value
- context mode: `group` or `isolated`
- `next_run`
- status

### Schedule computation

NanoClaw supports:

- cron schedules
- fixed interval schedules
- one-shot local timestamps

`computeNextRun(...)` deliberately anchors interval schedules to the previously
scheduled time rather than to "now". This avoids long-term drift.

### Scheduler loop

The scheduler loop wakes up every minute by default.

It:

- queries `getDueTasks()`
- re-checks current task status from SQLite
- enqueues execution into the `GroupQueue`

This means scheduled tasks share the same concurrency pool as message-driven
work.

### Task execution

A due task eventually calls `runContainerAgent(...)` just like message
processing.

Differences from normal message execution:

- the prompt is task-defined rather than built from inbound messages
- `context_mode=group` reuses the group's existing Claude session
- `context_mode=isolated` starts fresh without chat-session history
- results are forwarded to the target chat
- the task container is explicitly closed shortly after result delivery

### After execution

The host:

- writes a task run log row
- updates `last_run`
- updates `last_result`
- computes the next run time
- marks one-shot tasks as completed when no next run exists

## Scheduled Task Management

Task management also goes through the same MCP -> IPC -> host authorization
pipeline.

Supported operations:

- list tasks
- pause task
- resume task
- cancel task
- update task

The host enforces scope:

- main group can manage all tasks
- non-main groups can only manage their own tasks

## Recovery and Failure Behavior

NanoClaw includes lightweight recovery mechanisms.

### Message recovery

If the host crashes after advancing the top-level `lastTimestamp` but before the
group has actually been processed, `recoverPendingMessages()` scans for messages
after each group's `lastAgentTimestamp` and re-enqueues those groups.

This is how NanoClaw compensates for having:

- SQLite as durable inbound storage
- an in-memory execution queue

### Retry behavior

Group message processing failures get exponential backoff retries in
`GroupQueue`.

The retry state is in memory, not durable.

### Container cleanup

On startup NanoClaw tries to clean up orphaned `nanoclaw-*` containers.

On shutdown it detaches from active containers instead of killing them
aggressively. The idea is that they will finish and `--rm` will remove them.

## Design Characteristics

### What NanoClaw optimizes for

- simplicity of deployment on one machine
- inspectable control flow
- strong isolation around agent execution
- per-group state separation
- reuse of Claude Code / Claude Agent SDK rather than inventing a custom agent
  runtime

### What NanoClaw does not optimize for

- horizontal scaling
- distributed scheduling
- high-availability failover
- durable multi-host worker coordination
- event-driven low-latency pipelines

This is intentionally a local-first orchestration design.

## Important Architectural Insights

### 1. The "queue" is split between SQLite and memory

Inbound durability is SQLite. Execution ordering and concurrency are in memory.
You need both pieces to understand how NanoClaw works.

### 2. The container is not the orchestrator

The host remains the authority. Containers execute Claude and request actions,
but the host decides what is allowed and applies it.

### 3. The filesystem is the integration bus

NanoClaw uses the filesystem heavily:

- bind mounts for workspace exposure
- per-group IPC directories for commands
- per-group snapshots for tasks and groups
- per-group `.claude` state

This is one of the most distinctive aspects of the design.

### 4. Warm conversational containers are a major behavior

NanoClaw is not purely request/response at the container layer. A group's
container can remain alive, keep session continuity, and receive more messages
through IPC until the host decides to close it.

### 5. Privilege is encoded through group identity

The main group is effectively an admin/control context. Regular groups are more
restricted. A lot of NanoClaw behavior only makes sense once this distinction is
understood.

## Implications For A Similar System

If the goal is to reproduce the NanoClaw pattern in another project, the
essential ingredients are:

- a durable inbound event store
- a per-conversation execution queue
- a containerized agent runtime
- a host-only secret proxy
- a host-authoritative IPC control plane
- a persistent per-group session/memory layout

The design is especially good if you want:

- one-machine operation
- transparent behavior
- straightforward debugging by inspecting files and SQLite state
- strong separation between orchestration and agent execution

The design is less suitable if you need:

- many workers across many hosts
- central queue infrastructure
- hard real-time scheduling
- stateless elastic execution

## Concise Mental Model

The cleanest way to think about NanoClaw is:

"A local Node.js control process that stores inbound messages in SQLite, decides
when each conversation should run, launches a Docker-isolated Claude Agent SDK
session for that conversation, and uses bind-mounted files plus per-group IPC
directories to let the agent read workspace state and ask the host to perform
authorized actions."
