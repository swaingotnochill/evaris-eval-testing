from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import model_graded_qa
from inspect_ai.solver import TaskState, Generate, solver

from agents.support_agent import run_agent

SAMPLES_PATH = Path(__file__).with_name("samples.jsonl")


@solver
def langchain_agent_solver():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        del generate
        answer = run_agent(str(state.input))
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
