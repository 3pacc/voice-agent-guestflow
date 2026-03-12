from typing import TypedDict, Annotated, List, Literal
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from src.llm.vllm_client import VllmClient

class ChatState(TypedDict):
    """
    State representing the current conversation and booking context.
    """
    messages: Annotated[List[BaseMessage], "The conversation history"]
    stage: str # greeting, dates_collection, availability_check, confirmation
    check_in_date: str | None
    check_out_date: str | None
    guests: int | None
    room_available: bool | None

SYSTEM_PROMPT = """You are a polite, helpful, and concise virtual hotel receptionist for GuestFlow Hotel.
Your job is to help users book a room.
Keep your answers brief as they are spoken over the phone.
If you need more info (dates, guests), ask one question at a time.
Once you have the check-in date, check-out date, and number of guests, say 'Checking availability...' and stop.
Do not invent room details until given confirmation."""

def run_llm_node(state: ChatState) -> dict:
    """
    Main LLM processing node to determine next reply or action.
    This would ordinarily use an LLM with tool calling or a specialized prompt.
    For streaming compatibility, the node generates text.
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    
    # In a fully real-time streaming graph, we just return the updated state.
    # The actual stream happens out-of-band or via LangGraph's stream events.
    # For now, we mock the logic.
    last_human_message = state["messages"][-1].content.lower() if state["messages"] else ""
    
    # Very rudimentary state machine fallback
    if state["stage"] == "greeting":
        next_stage = "dates_collection"
    elif "tomorrow" in last_human_message or "january" in last_human_message:
        next_stage = "availability_check"
    else:
        next_stage = state["stage"]
        
    return {"stage": next_stage}

def build_graph() -> StateGraph:
    graph = StateGraph(ChatState)
    
    graph.add_node("llm", run_llm_node)
    
    graph.add_edge(START, "llm")
    graph.add_edge("llm", END)
    
    return graph.compile()

booking_agent = build_graph()
