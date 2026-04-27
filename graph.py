from langgraph.graph import StateGraph, END

from state import DPState
from nodes.initialize import initialize_node
from nodes.generator import generator_node
from nodes.breaker import breaker_node
from nodes.executor import executor_node
from nodes.scorer import scorer_node
from nodes.evolver import evolver_node
from nodes.terminator import terminator_node


def build_graph() -> StateGraph:
    builder = StateGraph(DPState)

    # 1. Define Nodes
    builder.add_node("initialize", initialize_node)
    builder.add_node("generator",  generator_node)
    builder.add_node("breaker",    breaker_node)
    builder.add_node("executor",   executor_node)
    builder.add_node("scorer",     scorer_node)
    builder.add_node("evolver",    evolver_node)
    builder.add_node("terminator", terminator_node)

    # 2. Define Standard Edges
    builder.set_entry_point("initialize")
    builder.add_edge("initialize", "generator")
    builder.add_edge("generator",  "breaker")
    builder.add_edge("breaker",    "executor")
    builder.add_edge("executor",   "scorer")
    builder.add_edge("scorer",     "evolver")
    builder.add_edge("evolver",    "terminator")

    # 3. Define Conditional Routing (Masterbook Ch. 3.2 exact)
    def route_verdict(state: DPState) -> str:
        if state["af_class"] in ("antifragile", "correct", "brittle", "degraded"):
            return "done"
        if state["current_round"] >= state["max_rounds"]:
            return "done"
        return "loop"

    builder.add_conditional_edges(
        "terminator",
        route_verdict,
        {"loop": "generator", "done": END},
    )

    return builder.compile()


darwin_phoenix = build_graph()
