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
    "What needs my attention?",
    "Is October ready to close?",
    "Why is my October entry for 2482 flagged?",
    "What if I enter 4000 KS for 2482 in October?",
    "Please submit 4000 KS for 2482 in October, range 3800 to 4200, because Corteva dropped its blocky variety",
    "Justify my October IBP number for 2432: two cooperatives confirmed bookings",
    "Approve Rep A's October entry for 2482",
    "Make a rule: do not accept autumn increases above 20% over last year unless the rep names a competitor move",
    "What is range coverage?",
    "How do I justify an IBP entry?",
]


async def main() -> None:
    provider = get_decision_provider()
    for question in QUESTIONS:
        intent, source = await provider.classify_chat_intent(question, DecisionPolicy(allow_jev=True))
        print(f"{intent:<22} {source:<18} {question}")


if __name__ == "__main__":
    asyncio.run(main())
