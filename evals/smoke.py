"""Cheap pipeline check: two questions, real model calls, substring scoring.
"""
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import includes


@task
def smoke():
    return Task(
        dataset=[
            Sample(input="What is 2+2? Answer with just the number.", target="4"),
            Sample(input="What is the capital of France? One word only.", target="Paris"),
        ],
        scorer=includes(),
    )
