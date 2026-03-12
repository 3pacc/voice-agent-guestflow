import pytest
from src.agent.booking_graph import booking_agent
from langchain_core.messages import HumanMessage
import asyncio

@pytest.mark.asyncio
async def test_langgraph_flow():
    state = {
        "messages": [HumanMessage(content="Hello, I want to book a room.")],
        "stage": "greeting",
        "check_in_date": None,
        "check_out_date": None,
        "guests": None,
        "room_available": None
    }
    
    new_state = await booking_agent.ainvoke(state)
    assert new_state["stage"] == "dates_collection"

    # Simulate next turn
    state["stage"] = new_state["stage"]
    state["messages"].append(HumanMessage(content="I want to stay tomorrow for 3 nights."))
    new_state = await booking_agent.ainvoke(state)
    
    assert new_state["stage"] == "availability_check"

if __name__ == "__main__":
    asyncio.run(test_langgraph_flow())
    print("Graph logic test passed!")
