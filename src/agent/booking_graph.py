import re
import logging
import datetime
from typing import TypedDict, Annotated, List, Literal

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from src.db.policy_rag import rag as policy_rag

logger = logging.getLogger(__name__)


class ChatState(TypedDict):
    """
    State representing the current conversation and booking context.
    """
    messages: Annotated[List[BaseMessage], "The conversation history"]
    stage: str  # greeting, dates_collection, availability_check, confirmation, done
    check_in_date: str | None
    check_out_date: str | None
    guests: int | None
    room_available: bool | None


SYSTEM_PROMPT = """You are a polite, helpful, and concise virtual hotel receptionist for GuestFlow Hotel.
Your job is to help users book a room.
Keep your answers brief as they are spoken over the phone.
If you need more info (dates, guests), ask one question at a time.
Once you have the check-in date, check-out date, and number of guests, confirm the details.
Do not invent room details until given confirmation."""


# ---------------------------------------------------------------------------
# Helpers: date & guest extraction from natural language
# ---------------------------------------------------------------------------

def _parse_date(text: str, reference: datetime.date | None = None) -> str | None:
    """Extract a date mention from text. Returns ISO string or None."""
    today = datetime.date.today()
    text = text.lower()

    if "today" in text:
        return str(today)
    if "tomorrow" in text:
        return str(today + datetime.timedelta(days=1))
    if "day after tomorrow" in text:
        return str(today + datetime.timedelta(days=2))

    # "in X days"
    m = re.search(r"in\s+(\d+)\s+days?", text)
    if m:
        return str(today + datetime.timedelta(days=int(m.group(1))))

    # "next monday/tuesday/..."
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day_name in enumerate(weekdays):
        if f"next {day_name}" in text or day_name in text:
            days_ahead = (i - today.weekday() + 7) % 7 or 7
            return str(today + datetime.timedelta(days=days_ahead))

    # ISO date: YYYY-MM-DD
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if m:
        return m.group(1)

    # "March 20", "20 March", "20/03", "03/20"
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for month_name, month_num in months.items():
        patterns = [
            rf"{month_name}\s+(\d{{1,2}})",
            rf"(\d{{1,2}})\s+{month_name}",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                day = int(m.group(1))
                year = today.year
                candidate = datetime.date(year, month_num, day)
                if candidate < today:
                    candidate = datetime.date(year + 1, month_num, day)
                return str(candidate)

    return None


def _parse_nights(text: str) -> int | None:
    """Extract number of nights from text."""
    m = re.search(r"(\d+)\s*nights?", text.lower())
    if m:
        return int(m.group(1))
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "a week": 7}
    for word, num in words.items():
        if word in text.lower():
            return num
    return None


def _parse_guests(text: str) -> int | None:
    """Extract number of guests from text."""
    m = re.search(r"(\d+)\s*(person|people|guest|adult|pax|passenger)", text.lower())
    if m:
        return int(m.group(1))
    words = {"just me": 1, "myself": 1, "alone": 1,
             "two": 2, "couple": 2, "three": 3, "four": 4}
    for word, num in words.items():
        if word in text.lower():
            return num
    return None


def _is_policy_question(text: str) -> bool:
    """Returns True if the user is asking about hotel policies."""
    policy_keywords = [
        "pet", "dog", "cat", "breakfast", "food", "cancel", "refund",
        "check-in time", "checkout time", "check out time", "check in time",
        "late", "early", "parking", "wifi", "policy", "rule",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in policy_keywords)


# ---------------------------------------------------------------------------
# LangGraph Nodes
# ---------------------------------------------------------------------------

def parse_intent_node(state: ChatState) -> dict:
    """
    Parses the last user message to extract dates, guests, and stage transitions.
    Updates state fields without calling the LLM (fast, no-latency node).
    """
    if not state["messages"]:
        return {"stage": "greeting"}

    last_msg = state["messages"][-1]
    if not isinstance(last_msg, HumanMessage):
        return {}

    text = last_msg.content
    updates: dict = {}

    # --- Extract check-in date ---
    if state["check_in_date"] is None:
        ci = _parse_date(text)
        if ci:
            updates["check_in_date"] = ci
            logger.info(f"Detected check-in: {ci}")

    # --- Extract nights → compute check-out ---
    if state.get("check_in_date") or updates.get("check_in_date"):
        ci_str = updates.get("check_in_date") or state["check_in_date"]
        if state["check_out_date"] is None:
            nights = _parse_nights(text)
            if nights:
                ci = datetime.date.fromisoformat(ci_str)
                co = ci + datetime.timedelta(days=nights)
                updates["check_out_date"] = str(co)
                logger.info(f"Computed check-out: {co} ({nights} nights)")

    # --- Extract guests ---
    if state["guests"] is None:
        guests = _parse_guests(text)
        if guests:
            updates["guests"] = guests
            logger.info(f"Detected guests: {guests}")

    # --- Stage transition ---
    ci = updates.get("check_in_date") or state["check_in_date"]
    co = updates.get("check_out_date") or state["check_out_date"]
    guests = updates.get("guests") or state["guests"]

    if state["stage"] == "greeting":
        updates["stage"] = "dates_collection"
    elif ci and co and guests:
        updates["stage"] = "availability_check"
    
    return updates


def check_availability_node(state: ChatState) -> dict:
    """
    Checks room availability in SQLite and appends the result to messages
    so the LLM can use it in its next spoken response.
    """
    from src.db.sql_stock import check_availability

    ci = datetime.date.fromisoformat(state["check_in_date"])
    co = datetime.date.fromisoformat(state["check_out_date"])

    available = check_availability(ci, co)
    logger.info(f"Availability check {ci} → {co}: {available}")

    if available:
        tool_msg = AIMessage(content=(
            f"[System] Room available from {state['check_in_date']} to "
            f"{state['check_out_date']} for {state['guests']} guest(s). "
            "Confirm the booking with the user."
        ))
    else:
        tool_msg = AIMessage(content=(
            f"[System] No rooms available from {state['check_in_date']} to "
            f"{state['check_out_date']}. Apologise and ask for alternative dates."
        ))

    return {
        "room_available": available,
        "stage": "confirmation",
        "messages": state["messages"] + [tool_msg],
    }


def query_policy_node(state: ChatState) -> dict:
    """
    Answers hotel policy questions using the PolicyRAG knowledge base.
    Injects the answer as a system message so the LLM can relay it naturally.
    """
    last_msg = state["messages"][-1].content if state["messages"] else ""
    answer = policy_rag.query(last_msg)
    logger.info(f"PolicyRAG answer: {answer}")

    tool_msg = AIMessage(content=f"[System] Policy info for user: {answer}")
    return {"messages": state["messages"] + [tool_msg]}


def route_after_parse(state: ChatState) -> Literal["check_availability", "query_policy", "end"]:
    """Conditional routing after parsing intent."""
    last_msg = state["messages"][-1] if state["messages"] else None
    if last_msg and isinstance(last_msg, HumanMessage):
        if _is_policy_question(last_msg.content):
            return "query_policy"

    # Trigger availability check as soon as we have both dates (guests optional —
    # the LLM will ask verbally if still missing).
    if state["stage"] == "availability_check":
        if state["check_in_date"] and state["check_out_date"]:
            return "check_availability"

    return "end"


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(ChatState)

    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("check_availability", check_availability_node)
    graph.add_node("query_policy", query_policy_node)

    graph.add_edge(START, "parse_intent")
    graph.add_conditional_edges(
        "parse_intent",
        route_after_parse,
        {
            "check_availability": "check_availability",
            "query_policy": "query_policy",
            "end": END,
        },
    )
    graph.add_edge("check_availability", END)
    graph.add_edge("query_policy", END)

    return graph.compile()


booking_agent = build_graph()
