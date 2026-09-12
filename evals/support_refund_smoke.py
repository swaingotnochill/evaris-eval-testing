"""The real eval: LangChain support agent answering refund questions,
scored by a model-based judge. Agent, tools, and grader all make live model
calls. Mirrors tests/integration in the backend repo.

The solver bridges two worlds: LangGraph runs the agent (its own model
calls, invisible to Inspect), so we replay the agent's message history into
the inspect transcript — tool calls, tool results, and intermediate answers
all show up in the sample trace — and set the final answer as the output.
"""
from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ModelOutput
from inspect_ai.scorer import model_graded_qa
from inspect_ai.solver import TaskState, Generate, solver

from agents.support_agent import final_agent_answer, message_text, run_agent_messages

SAMPLES_PATH = Path(__file__).with_name("samples.jsonl")


def replay_agent_trace(messages: list) -> list:
    """LangGraph messages → inspect transcript messages (skipping the initial
    user turn, which is already the sample input)."""
    replayed = []
    for message in messages[1:]:
        kind = message.__class__.__name__
        text = message_text(message.content).strip()
        if kind == "AIMessage":
            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                # inspect's ToolCall is flat: function is the tool name,
                # arguments the parsed dict. Tool results link back via
                # tool_call_id (ChatMessageTool carries no name).
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
        del generate
        messages = run_agent_messages(str(state.input))
        answer = final_agent_answer(messages)
        trace = replay_agent_trace(messages)
        # The transcript must end with the exact answer being graded: when the
        # agent's last AIMessage was empty, the graded answer is an earlier
        # turn the replay already contains — don't duplicate it.
        if answer and (not trace or str(trace[-1].content).strip() != answer):
            trace.append(ChatMessageAssistant(content=answer))
        state.messages.extend(trace)
        state.output = ModelOutput.from_content(model="langchain-agent", content=answer)
        return state

    return solve


@task
def support_refund_smoke():
    return Task(
        dataset=json_dataset(str(SAMPLES_PATH)),
        solver=langchain_agent_solver(),
        scorer=model_graded_qa(),
    )
