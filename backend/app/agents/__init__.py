"""Multi-Agent Intelligence Council + AI Decision Engine.

Six specialized agents each analyse the same grounded context (live intel feed +
scenario simulation) and produce an evidence-linked assessment with confidence.
They are allowed to disagree. The Decision Engine reconciles them into ranked
national response strategies.

Every agent runs on the real LLM router when a key is configured, and on a
deterministic, simulation-grounded fallback reasoner otherwise — so the Council
is never empty and never hallucinates numbers.
"""

from app.agents.council import Council, get_council

__all__ = ["Council", "get_council"]
