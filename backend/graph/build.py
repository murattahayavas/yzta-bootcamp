"""
LangGraph orkestrasyonu — Sprint 2.

                         ┌── "tekli" ──► calculator ──► critic ──┬─► insight ──► END
planner ──(router)──┤                        ▲              │
                         └── "senaryo" ─► senaryo_calculator ─► senaryo_critic ─┤
                                              ▲                            │
                                              └────────── retry ◄──────────┘

Reflexion döngüsü her iki dalda da var: tekli hesap critic→retry→calculator,
senaryo karşılaştırmasında senaryo_critic→retry→senaryo_calculator (max 3).

Sprint 2 hafıza: `gecmis` state anahtarı, çağıran taraf (Flask) tarafından
önceki tur(lar)ın {soru, aciklama} kayıtlarıyla doldurularak geçirilir;
graph bunu sadece okur, kendi biriktirmez (backend'de konuşma oturum
bazlı tutulur).
"""
from __future__ import annotations

from typing import TypedDict, Any

from langgraph.graph import StateGraph, END

from agents.nodes import (
    planner_node, planner_router,
    calculator_node, critic_node, critic_router, retry_node,
    senaryo_calculator_node, senaryo_critic_node, senaryo_critic_router,
    insight_node,
)


class State(TypedDict, total=False):
    bilgi: Any
    soru: str
    gecmis: list
    plan: dict
    sonuclar: dict
    senaryolar: list
    ihlaller: list
    retry: int
    aciklama: str
    grafik: str | None
    demo_mode: bool


def build_graph():
    g = StateGraph(State)
    g.add_node("planner", planner_node)
    g.add_node("calculator", calculator_node)
    g.add_node("critic", critic_node)
    g.add_node("retry", retry_node)
    g.add_node("senaryo_calculator", senaryo_calculator_node)
    g.add_node("senaryo_critic", senaryo_critic_node)
    g.add_node("senaryo_retry", retry_node)
    g.add_node("insight", insight_node)

    g.set_entry_point("planner")
    g.add_conditional_edges("planner", planner_router, {
        "tekli": "calculator",
        "senaryo": "senaryo_calculator",
    })

    g.add_edge("calculator", "critic")
    g.add_conditional_edges("critic", critic_router, {"retry": "retry", "ok": "insight"})
    g.add_edge("retry", "calculator")

    g.add_edge("senaryo_calculator", "senaryo_critic")
    g.add_conditional_edges("senaryo_critic", senaryo_critic_router, {"retry": "senaryo_retry", "ok": "insight"})
    g.add_edge("senaryo_retry", "senaryo_calculator")

    g.add_edge("insight", END)
    return g.compile()


def run(bilgi, soru: str = "", gecmis: list | None = None) -> dict:
    app = build_graph()
    return app.invoke({"bilgi": bilgi, "soru": soru, "gecmis": gecmis or []})
