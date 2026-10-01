"""ADK evaluation of the data agent's tool trajectories. Needs live Gemini on Vertex, so it is opt-in."""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_EVAL") != "1" or not os.environ.get("GCP_PROJECT"),
    reason="set RUN_LIVE_EVAL=1, GCP_PROJECT and GEMINI_ENABLED=true to run the live ADK evalset",
)


async def test_data_agent_evalset(seeded: None) -> None:
    from google.adk.evaluation.agent_evaluator import AgentEvaluator

    await AgentEvaluator.evaluate(
        agent_module="app.ai.data_agent",
        eval_dataset_file_path_or_dir=str(Path(__file__).parent / "data_agent.evalset.json"),
        num_runs=1,
    )
