import pytest

from app.agents.council import Council


@pytest.mark.asyncio
async def test_langgraph_council_persists_workflow_and_mission() -> None:
    result = await Council().convene("hormuz_closure")
    assert result.workflow_run_id.startswith("wf-")
    assert result.mission_id and result.mission_id.startswith("msn-")
    assert len(result.assessments) == 6
    assert len(result.strategies) == 3
    assert result.schema_version == "1.0"
    assert result.strategies[0].procurement_alternatives
