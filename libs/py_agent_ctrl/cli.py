from __future__ import annotations

import argparse
from collections.abc import Callable

from py_agent_ctrl import AgentCtrl, AgentTextEvent
from py_agent_ctrl.actions.base import BaseAgentAction


def _resolve_agent(name: str) -> BaseAgentAction:
    agents: dict[str, Callable[[], BaseAgentAction]] = {
        "claude-code": AgentCtrl.claude_code,
        "codex": AgentCtrl.codex,
        "opencode": AgentCtrl.opencode,
        "pi": AgentCtrl.pi,
        "gemini": AgentCtrl.gemini,
    }
    try:
        return agents[name]()
    except KeyError as exc:
        raise SystemExit(f"Unsupported agent: {name}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ctrlagent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    execute = subparsers.add_parser("execute")
    execute.add_argument("--agent", required=True)
    execute.add_argument("prompt")

    stream = subparsers.add_parser("stream")
    stream.add_argument("--agent", required=True)
    stream.add_argument("prompt")

    resume = subparsers.add_parser("resume")
    resume.add_argument("--agent", required=True)
    resume.add_argument("--session", required=True)
    resume.add_argument("prompt")

    cont = subparsers.add_parser("continue")
    cont.add_argument("--agent", required=True)
    cont.add_argument("prompt")

    agents = subparsers.add_parser("agents")
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)
    agents_sub.add_parser("list")
    caps = agents_sub.add_parser("capabilities")
    caps.add_argument("--agent", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "agents":
        if args.agents_command == "list":
            for name in ("claude-code", "codex", "opencode", "pi", "gemini"):
                print(name)
            return 0
        action = _resolve_agent(args.agent)
        print(action.capabilities().model_dump_json(indent=2))
        return 0

    action = _resolve_agent(args.agent)
    if args.command == "resume":
        action = action.resume_session(args.session)
        response = action.execute(args.prompt)
        print(response.text)
        return response.exit_code
    if args.command == "continue":
        response = action.continue_session().execute(args.prompt)
        print(response.text)
        return response.exit_code
    if args.command == "stream":
        result = action.stream(args.prompt)
        for event in result:
            if isinstance(event, AgentTextEvent):
                print(event.text, end="")
        return result.exit_code

    response = action.execute(args.prompt)
    print(response.text)
    return response.exit_code
