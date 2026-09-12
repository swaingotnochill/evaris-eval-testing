from __future__ import annotations

import json
import os

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI


ORDERS = {
    "A100": {
        "item": "Noise-cancelling headphones",
        "status": "delivered",
        "delivered_days_ago": 12,
        "price_usd": 199,
        "condition": "unopened",
    },
    "B200": {
        "item": "Standing desk mat",
        "status": "delivered",
        "delivered_days_ago": 45,
        "price_usd": 89,
        "condition": "used",
    },
    "C300": {
        "item": "USB-C hub",
        "status": "in_transit",
        "delivered_days_ago": None,
        "price_usd": 49,
        "condition": "new",
    },
    "D400": {
        "item": "Mechanical keyboard",
        "status": "delivered",
        "delivered_days_ago": 8,
        "price_usd": 129,
        "condition": "defective",
    },
    "E500": {
        "item": "Ergonomic mouse",
        "status": "delivered",
        "delivered_days_ago": 20,
        "price_usd": 59,
        "condition": "opened",
    },
}


@tool
def lookup_order(order_id: str) -> str:
    """Look up order status, item, price, delivery age, and condition."""
    return json.dumps(ORDERS.get(order_id.upper(), {"error": "order_not_found"}))


@tool
def refund_policy(condition: str, delivered_days_ago: int | None) -> str:
    """Return refund policy guidance for an item's condition and delivery age."""
    if delivered_days_ago is None:
        return "Order has not been delivered yet. Refund is not available; offer shipment tracking."
    if condition == "defective" and delivered_days_ago <= 60:
        return "Eligible for full refund or replacement because defective items are covered for 60 days."
    if condition == "unopened" and delivered_days_ago <= 30:
        return "Eligible for full refund because unopened items are covered for 30 days."
    if condition == "opened" and delivered_days_ago <= 30:
        return "Eligible for partial refund up to 50 percent because opened items are within 30 days."
    return "Not eligible for self-serve refund. Escalate to human support if the customer disputes this."


@tool
def estimate_refund(price_usd: int, refund_type: str) -> str:
    """Estimate refund amount. refund_type must be full, partial, or none."""
    if refund_type == "full":
        return str(price_usd)
    if refund_type == "partial":
        return str(round(price_usd * 0.5))
    return "0"


@tool
def create_escalation_ticket(order_id: str, reason: str) -> str:
    """Create a mock human-support escalation ticket."""
    return f"ESC-{order_id.upper()}-{reason.lower().replace(' ', '-')}"


def create_support_agent():
    model = ChatOpenAI(
        model=os.environ.get("LANGCHAIN_AGENT_MODEL", "glm-4.5"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )
    return create_agent(
        model=model,
        tools=[lookup_order, refund_policy,
               estimate_refund, create_escalation_ticket],
        system_prompt=(
            "You are a support refund agent. Use tools before deciding. "
            "Return one concise sentence containing the decision and key amount or ticket id."
        ),
    )


def run_agent_messages(question: str) -> list:
    """Run the agent and return every LangGraph message (full trace)."""
    agent = create_support_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"]


def message_text(content) -> str:
    """Plain text from a LangChain content field (str or content blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        ).strip()
    return str(content)


def final_agent_answer(messages: list) -> str:
    """The last AIMessage that actually has text.

    langgraph occasionally ends the loop with an empty AIMessage (or a
    tool-only one), so blindly taking messages[-1] yields "" — which then
    fails grading through no fault of the agent.
    """
    for message in reversed(messages):
        if message.__class__.__name__ != "AIMessage":
            continue
        text = message_text(message.content).strip()
        if text:
            return text
    return ""


def run_agent(question: str) -> str:
    return final_agent_answer(run_agent_messages(question))
