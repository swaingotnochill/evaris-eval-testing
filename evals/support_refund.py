"""Support-agent refund eval.

The system under test is the LangChain agent in agents/support_agent.py — a
Python module in this repo, so the solver invokes it in-process rather than
over HTTP. The agent runs its own model loop (invisible to Inspect), so we
replay its LangGraph message history into the inspect transcript: tool calls,
tool results, and intermediate answers all show up in the sample trace in
Evaris, and the final answer becomes the graded output.

Scoring is model_graded_qa: an LLM judge compares the agent's one-sentence
answer against each sample's target criterion.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make agents/ importable no matter where inspect is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ModelOutput
from inspect_ai.scorer import model_graded_qa
from inspect_ai.solver import Generate, TaskState, solver

from agents.support_agent import final_agent_answer, message_text, run_agent_messages

SAMPLES_PATH = Path(__file__).with_name("samples.jsonl")


def replay_agent_trace(messages: list) -> list:
    """LangGraph messages → inspect transcript messages.

    Skips the initial user turn (already the sample input). Ensures the
    transcript ends with the exact text being graded.
    """
    replayed = []
    for message in messages[1:]:
        kind = message.__class__.__name__
        text = message_text(message.content).strip()
        if kind == "AIMessage":
            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                replayed.append(
                    ChatMessageAssistant(
                        content=text,
                        tool_calls=[
                            {
                                "id": call["id"],
                                "function": call["name"],
                                "arguments": call["args"],
                            }
                            for call in tool_calls
                        ],
                    )
                )
            elif text:
                replayed.append(ChatMessageAssistant(content=text))
        elif kind == "ToolMessage":
            replayed.append(
                ChatMessageTool(
                    content=text,
                    tool_call_id=getattr(message, "tool_call_id", "") or "",
                )
            )
    return replayed


@solver
def langchain_agent_solver():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        del generate  # the agent's model loop runs inside run_agent_messages
        messages = run_agent_messages(str(state.input))
        answer = final_agent_answer(messages)
        state.messages.extend(replay_agent_trace(messages))
        state.output = ModelOutput.from_content(model="langchain-agent", content=answer)
        return state

    return solve


@task
def support_refund():
    return Task(
        dataset=json_dataset(str(SAMPLES_PATH)),
        solver=langchain_agent_solver(),
        scorer=model_graded_qa(),
    )
