import datetime
import logging
import re
import unicodedata
from typing import Annotated, List, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from src.db.policy_rag import rag as policy_rag

logger = logging.getLogger(__name__)


def _strip_accents(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', value) if unicodedata.category(c) != 'Mn')


def _word_to_int(token: str) -> int | None:
    mapping = {
        'un': 1,
        'une': 1,
        'deux': 2,
        'trois': 3,
        'quatre': 4,
        'cinq': 5,
    }
    return mapping.get(token)


class ChatState(TypedDict):
    """Conversation state for booking flow."""

    messages: Annotated[List[BaseMessage], "The conversation history"]
    stage: str  # greeting, details_collection, availability_check, confirmation, done
    check_in_date: str | None
    check_out_date: str | None
    nights: int | None
    guests: int | None
    room_type: str | None
    room_available: bool | None
    available_rooms: int | None
    price_per_night_eur: int | None
    total_price_eur: int | None


SYSTEM_PROMPT = """Tu es l'agent vocal de reservation de GuestFlow Hotel.

Objectif principal:
- Qualifier et finaliser une reservation avec une conversation fluide, professionnelle et dynamique.

Langue et ton:
- Reponds toujours en francais naturel (sauf demande explicite d'une autre langue).
- Reste chaleureux, premium, concis, et adapte a l'oral telephone.
- Une seule question ciblee a la fois.

Champs de reservation a collecter:
1) Date d'arrivee
2) Date de depart OU nombre de nuitees
3) Nombre de personnes
4) Type de chambre (standard, suite, deluxe, familiale)

Regles de conduite:
- N'invente jamais la disponibilite ni la politique hoteliere.
- Appuie-toi uniquement sur les messages systeme injectes par les outils.
- Les tarifs et disponibilites proviennent exclusivement de la base de donnees hoteliere.
- PRIORITE ABSOLUE: reponds d'abord a la derniere question du client.
- Si le client demande le prix/tarif/cout, donne d'abord le prix (EUR/nuit + total), puis propose la confirmation en une seule phrase.
- Ne repete jamais en boucle: "Souhaitez-vous confirmer...".
- Si une information manque, demande uniquement cette information.
- Ne salue jamais a nouveau apres le message de bienvenue initial.
- Ne fais pas de recapitulatif complet a chaque tour; fais-le uniquement quand la disponibilite est confirmee, puis demande la confirmation.
- Quand la disponibilite est confirmee, annonce le prix en euros (prix/nuit et total) puis propose une offre commerciale pertinente.
- Utilise des techniques de negociation douces: valoriser l'offre, creer de la confiance, proposer une option avantageuse (ex: petit-dejeuner inclus).
- Si indisponible, excuse-toi et propose des alternatives concretes (autres dates / autre type de chambre).
"""


def _safe_date(year: int, month: int, day: int) -> datetime.date | None:
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def _parse_date_range(text: str, reference: datetime.date | None = None) -> tuple[str | None, str | None]:
    """Parse expressions like 'du 20 au 22 mars' or 'du 20/03 au 22/03'."""
    today = reference or datetime.date.today()
    low = _strip_accents((text or '').lower())

    m = re.search(r"du\s+(\d{1,2})(?:[/-](\d{1,2}))?\s+au\s+(\d{1,2})(?:[/-](\d{1,2}))?(?:[/-](\d{2,4}))?", low)
    if not m:
        return (None, None)

    d1 = int(m.group(1))
    m1 = int(m.group(2)) if m.group(2) else None
    d2 = int(m.group(3))
    m2 = int(m.group(4)) if m.group(4) else m1
    y = int(m.group(5)) if m.group(5) else today.year
    if y < 100:
        y += 2000

    if not m1 or not m2:
        month_guess = today.month
        m1 = m1 or month_guess
        m2 = m2 or month_guess

    ci = _safe_date(y, m1, d1)
    co = _safe_date(y, m2, d2)
    if not ci or not co:
        return (None, None)
    if co <= ci:
        co = _safe_date(y + 1, m2, d2)
        if not co or co <= ci:
            return (None, None)

    return (str(ci), str(co))


def _parse_date(text: str, reference: datetime.date | None = None) -> str | None:
    today = reference or datetime.date.today()
    low = text.lower().strip()

    if "aujourd'hui" in low or "today" in low:
        return str(today)
    if "demain" in low or "tomorrow" in low:
        return str(today + datetime.timedelta(days=1))
    if "apres-demain" in low or "apr?s-demain" in low or "day after tomorrow" in low:
        return str(today + datetime.timedelta(days=2))

    m = re.search(r"(?:dans|in)\s+(\d+)\s+(?:jours?|days?)", low)
    if m:
        return str(today + datetime.timedelta(days=int(m.group(1))))

    weekdays = {
        "lundi": 0,
        "monday": 0,
        "mardi": 1,
        "tuesday": 1,
        "mercredi": 2,
        "wednesday": 2,
        "jeudi": 3,
        "thursday": 3,
        "vendredi": 4,
        "friday": 4,
        "samedi": 5,
        "saturday": 5,
        "dimanche": 6,
        "sunday": 6,
    }
    for name, idx in weekdays.items():
        if f"next {name}" in low or f"{name} prochain" in low or re.search(rf"\b{name}\b", low):
            days_ahead = (idx - today.weekday() + 7) % 7 or 7
            return str(today + datetime.timedelta(days=days_ahead))

    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", low)
    if m:
        return m.group(1)

    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", low)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        if year < 100:
            year += 2000
        candidate = _safe_date(year, month, day)
        if not candidate:
            return None
        if not m.group(3) and candidate < today:
            candidate = _safe_date(today.year + 1, month, day)
        return str(candidate) if candidate else None

    months = {
        "janvier": 1,
        "january": 1,
        "fevrier": 2,
        "f?vrier": 2,
        "february": 2,
        "mars": 3,
        "march": 3,
        "avril": 4,
        "april": 4,
        "mai": 5,
        "may": 5,
        "juin": 6,
        "june": 6,
        "juillet": 7,
        "july": 7,
        "aout": 8,
        "ao?t": 8,
        "august": 8,
        "septembre": 9,
        "september": 9,
        "octobre": 10,
        "october": 10,
        "novembre": 11,
        "november": 11,
        "decembre": 12,
        "d?cembre": 12,
        "december": 12,
    }
    for month_name, month_num in months.items():
        for pat in [rf"{month_name}\s+(\d{{1,2}})", rf"(\d{{1,2}})\s+{month_name}"]:
            m = re.search(pat, low)
            if not m:
                continue
            day = int(m.group(1))
            candidate = _safe_date(today.year, month_num, day)
            if not candidate:
                continue
            if candidate < today:
                candidate = _safe_date(today.year + 1, month_num, day)
            return str(candidate) if candidate else None

    return None


def _parse_nights(text: str) -> int | None:
    low = text.lower()
    m = re.search(r"(\d+)\s*(?:nuits?|nights?)", low)
    if m:
        return int(m.group(1))

    words = {
        "une nuit": 1,
        "one night": 1,
        "deux": 2,
        "two": 2,
        "trois": 3,
        "three": 3,
        "quatre": 4,
        "four": 4,
        "cinq": 5,
        "five": 5,
        "une semaine": 7,
        "a week": 7,
    }
    for word, num in words.items():
        if word in low:
            return num
    return None


def _parse_guests(text: str) -> int | None:
    low = text.lower()
    norm = _strip_accents(low)

    # Pattern: "2 adultes et 1 enfant" -> 3
    parts = re.findall(r"(\d+)\s*(adultes?|adults?|personnes?|people|enfants?|children|kids?|kid|bebes?|bebes)", norm)
    if parts:
        total = sum(int(n) for n, _ in parts)
        if total > 0:
            return total

    # Pattern with number words: "trois personnes"
    m_words = re.search(
        r"\b(un|une|deux|trois|quatre|cinq)\s*(?:personne|personnes|adultes?|guests?|people|pax|clients?)\b",
        norm,
    )
    if m_words:
        v = _word_to_int(m_words.group(1))
        if v:
            return v

    # Pattern with digits: "3 personnes"
    m = re.search(
        r"(\d+)\s*(?:personne|personnes|adultes?|guests?|people|pax|clients?)",
        norm,
    )
    if m:
        return int(m.group(1))

    # Special: "un couple et un enfant" / "couple avec enfant"
    if 'couple' in norm and any(k in norm for k in ['enfant', 'enfants', 'child', 'children', 'kid', 'kids', 'bebe', 'bebes']):
        return 3

    words = {
        'seul': 1,
        'seule': 1,
        'just me': 1,
        'couple': 2,
        'deux': 2,
        'two': 2,
        'trois': 3,
        'three': 3,
        'quatre': 4,
        'four': 4,
    }
    for word, num in words.items():
        if word in norm:
            return num
    return None


def _parse_room_type(text: str) -> str | None:
    low = text.lower()

    # Priority order from specific to generic
    if any(k in low for k in ["suite", "junior suite"]):
        return "suite"
    if any(k in low for k in ["deluxe", "de luxe"]):
        return "deluxe"
    if any(k in low for k in ["familiale", "family", "family room"]):
        return "familiale"
    if any(k in low for k in ["standard", "classique"]):
        return "standard"

    return None


def _is_policy_question(text: str) -> bool:
    low = text.lower()
    policy_keywords = [
        "pet",
        "dog",
        "cat",
        "animaux",
        "breakfast",
        "petit dejeuner",
        "petit-d?jeuner",
        "cancel",
        "annulation",
        "refund",
        "remboursement",
        "check-in",
        "check-out",
        "horaire",
        "heure",
        "parking",
        "wifi",
        "politique",
        "regle",
        "r?gle",
    ]
    return any(k in low for k in policy_keywords)


def parse_intent_node(state: ChatState) -> dict:
    if not state["messages"]:
        return {"stage": "greeting"}

    last_msg = state["messages"][-1]
    if not isinstance(last_msg, HumanMessage):
        return {}

    text = last_msg.content
    updates: dict = {}

    # Parse date range first when user gives both dates in one sentence.
    range_ci, range_co = _parse_date_range(text)
    if range_ci and range_co:
        if str(range_ci) != str(state.get("check_in_date")):
            logger.info(f"Detected check-in update: {state.get('check_in_date')} -> {range_ci}")
        if str(range_co) != str(state.get("check_out_date")):
            logger.info(f"Detected check-out update: {state.get('check_out_date')} -> {range_co}")
        updates["check_in_date"] = range_ci
        updates["check_out_date"] = range_co
        ci_dt = datetime.date.fromisoformat(range_ci)
        co_dt = datetime.date.fromisoformat(range_co)
        updates["nights"] = (co_dt - ci_dt).days

    # Allow check-in update when user explicitly gives new stay dates
    ci = _parse_date(text)
    if ci:
        ci_keywords = [
            "du ",
            "arrive",
            "arriv?e",
            "check-in",
            "checkin",
            "s?jour",
            "sejour",
        ]
        if state["check_in_date"] is None or any(k in text.lower() for k in ci_keywords):
            if str(ci) != str(state.get("check_in_date")):
                logger.info(f"Detected check-in update: {state.get('check_in_date')} -> {ci}")
            updates["check_in_date"] = ci

    # Allow guest count updates if user changes preference mid-conversation
    guests = _parse_guests(text)
    if guests:
        if guests != state.get("guests"):
            logger.info(f"Detected guests update: {state.get('guests')} -> {guests}")
        updates["guests"] = guests

    # Always re-parse room type so user can switch alternative (suite/standard/etc.)
    room_type = _parse_room_type(text)
    if room_type:
        if room_type != state.get("room_type"):
            logger.info(f"Detected room_type update: {state.get('room_type')} -> {room_type}")
        updates["room_type"] = room_type

    ci_str = updates.get("check_in_date") or state.get("check_in_date")

    if ci_str:
        # explicit departure date (allow updates if user changes dates)
        if any(k in text.lower() for k in ["depart", "d?part", "check-out", "checkout", "departure", " au "]):
            maybe_co = _parse_date(text)
            if maybe_co:
                ci = datetime.date.fromisoformat(ci_str)
                co = datetime.date.fromisoformat(maybe_co)
                if co > ci:
                    if str(co) != str(state.get("check_out_date")):
                        logger.info(
                            f"Detected check-out update: {state.get('check_out_date')} -> {co} ({(co - ci).days} nights)"
                        )
                    updates["check_out_date"] = str(co)
                    updates["nights"] = (co - ci).days

        # nights -> compute checkout (allow updates when user says new nights)
        nights = _parse_nights(text)
        if nights:
            ci = datetime.date.fromisoformat(ci_str)
            co = ci + datetime.timedelta(days=nights)
            if str(co) != str(state.get("check_out_date")):
                logger.info(
                    f"Computed check-out update: {state.get('check_out_date')} -> {co} ({nights} nights)"
                )
            updates["check_out_date"] = str(co)
            updates["nights"] = nights

    # stage transition
    ci = updates.get("check_in_date") or state.get("check_in_date")
    co = updates.get("check_out_date") or state.get("check_out_date")
    guests = updates.get("guests") or state.get("guests")
    room_type = updates.get("room_type") or state.get("room_type")

    booking_fields_changed = any(
        k in updates for k in ("check_in_date", "check_out_date", "nights", "guests", "room_type")
    )

    if state["stage"] == "greeting":
        updates["stage"] = "details_collection"
    elif state["stage"] == "done":
        pass
    elif ci and co and guests and room_type and (
        state["stage"] == "details_collection" or booking_fields_changed
    ):
        updates["stage"] = "availability_check"
        updates["room_available"] = None
        updates["available_rooms"] = None
        updates["price_per_night_eur"] = None
        updates["total_price_eur"] = None

    return updates


def check_availability_node(state: ChatState) -> dict:
    from src.db.sql_stock import check_availability_details

    ci = datetime.date.fromisoformat(state["check_in_date"])
    co = datetime.date.fromisoformat(state["check_out_date"])
    room_type = state.get("room_type") or "standard"
    guests = state.get("guests")

    details = check_availability_details(ci, co, room_type=room_type, guests=guests)
    available = bool(details.get("available"))
    nights = int(details.get("nights") or max((co - ci).days, 0))
    available_rooms = int(details.get("min_available_rooms") or 0)
    price_per_night_eur = details.get("price_per_night_eur")
    total_price_eur = details.get("total_price_eur")

    logger.info(
        "Availability check %s -> %s room_type=%s guests=%s => %s",
        ci,
        co,
        room_type,
        guests,
        details,
    )

    if available:
        tool_msg = AIMessage(
            content=(
                f"[System] Disponibilite OK (source DB) pour une chambre {details.get('room_type')} du {state['check_in_date']} "
                f"au {state['check_out_date']} ({nights} nuit(s)) pour {state.get('guests')} personne(s). "
                f"Stock minimum restant sur la periode: {available_rooms} chambre(s). "
                f"Tarif ferme DB: {price_per_night_eur} EUR par nuit, soit {total_price_eur} EUR au total. "
                "Reponds de facon concise et commerciale, sans inventer d'autres tarifs."
            )
        )
        next_stage = "confirmation"
    else:
        alternatives = details.get("alternatives") or []
        alt_text = ", ".join(
            f"{a.get('room_type')} (cap {a.get('capacity')}, {a.get('price_eur')} EUR/nuit)" for a in alternatives[:3]
        )
        if not alt_text:
            alt_text = "aucune alternative immediate"
        tool_msg = AIMessage(
            content=(
                f"[System] Disponibilite KO (source DB) pour une chambre {details.get('room_type')} du {state['check_in_date']} "
                f"au {state['check_out_date']} ({nights} nuit(s)). "
                f"Motif: {details.get('reason')}. Alternatives possibles: {alt_text}. "
                "Propose une alternative concrete sans demander confirmation maintenant."
            )
        )
        next_stage = "details_collection"

    return {
        "room_available": available,
        "available_rooms": available_rooms,
        "price_per_night_eur": price_per_night_eur,
        "total_price_eur": total_price_eur,
        "stage": next_stage,
        "messages": state["messages"] + [tool_msg],
    }


def query_policy_node(state: ChatState) -> dict:
    last_msg = state["messages"][-1].content if state["messages"] else ""
    answer = policy_rag.query(last_msg)
    logger.info(f"PolicyRAG answer: {answer}")

    tool_msg = AIMessage(content=f"[System] Information politique hoteliere: {answer}")
    return {"messages": state["messages"] + [tool_msg]}


def route_after_parse(state: ChatState) -> Literal["check_availability", "query_policy", "end"]:
    last_msg = state["messages"][-1] if state["messages"] else None
    if last_msg and isinstance(last_msg, HumanMessage) and _is_policy_question(last_msg.content):
        return "query_policy"

    if state["stage"] == "availability_check":
        if state.get("check_in_date") and state.get("check_out_date") and state.get("guests") and state.get("room_type"):
            return "check_availability"

    return "end"


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
