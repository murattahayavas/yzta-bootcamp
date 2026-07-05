"""
LangGraph orkestrasyonu.

    planner ──► calculator ──► critic ──┬─► insight ──► END
                    ▲                   │
                    └────── retry ◄─────┘  (ihlal varsa, max 3 deneme)

Reflexion döngüsü critic → retry → calculator kenarıdır. Sprint 1'de
deterministik motor ihlal üretmediği için döngü pratikte tetiklenmez;
Sprint 2'de LLM-üretimli hesap adımları eklendiğinde bu kenar projenin
kalbi olacak.
"""
from __future__ import annotations

from typing import TypedDict, Any

from langgraph.graph import StateGraph, END

from agents.nodes import (
    planner_node, calculator_node, critic_node, critic_router,
    retry_node, insight_node,
)


class State(TypedDict, total=False):
    bilgi: Any          # CalismaBilgisi
    soru: str
    plan: dict
    sonuclar: dict
    ihlaller: list
    retry: int
    aciklama: str
    demo_mode: bool


def build_graph():
    g = StateGraph(State)
    g.add_node("planner", planner_node)
    g.add_node("calculator", calculator_node)
    g.add_node("critic", critic_node)
    g.add_node("retry", retry_node)
    g.add_node("insight", insight_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "calculator")
    g.add_edge("calculator", "critic")
    g.add_conditional_edges("critic", critic_router, {"retry": "retry", "ok": "insight"})
    g.add_edge("retry", "calculator")
    g.add_edge("insight", END)
    return g.compile()


def run(bilgi, soru: str = "") -> dict:
    app = build_graph()
    return app.invoke({"bilgi": bilgi, "soru": soru})
