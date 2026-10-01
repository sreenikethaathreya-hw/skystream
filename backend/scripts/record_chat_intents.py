"""Record Jev's chat-intent decisions for the sample questions into tests/fixtures/ai/chat_intent/.

Run with a Jev key: `JEV_API_KEY=... AI_MODE=record uv run python scripts/record_chat_intents.py`.
"""

import asyncio

from app.ai.decision_provider import DecisionPolicy, get_decision_provider

QUESTIONS = [
    "What is the share for 2482 in October?",
    "How is 2432 tracking against plan month by month?",
    "Which of my entries were flagged?",
    "Has Rep B been accurate this year?",
    "Which competitor has the largest share?",
    "Which lead rules are active?",
    "Which exceptions are still open?",
    "Can you forecast October demand for 2482?",
]


async def main() -> None:
    provider = get_decision_provider()
    for question in QUESTIONS:
        intent, source = await provider.classify_chat_intent(question, DecisionPolicy(allow_jev=True))
        print(f"{intent:<22} {source:<18} {question}")


if __name__ == "__main__":
    asyncio.run(main())
