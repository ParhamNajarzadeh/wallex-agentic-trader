"""LangGraph `StateGraph` compilation with `MemorySaver`, conditional routing, `interrupt`, and Langfuse tracing."""

from __future__ import annotations

from typing import Any, Callable

from src.graph.nodes import TradingGraphNodes
from src.graph.state import TradingState

try:
    from langgraph.checkpoint.memory import MemorySaver  # type: ignore[import-not-found]
    from langgraph.graph import END, START, StateGraph  # type: ignore[import-not-found]

    HAS_NATIVE_LANGGRAPH = True
except Exception:
    HAS_NATIVE_LANGGRAPH = False
    START = "__start__"
    END = "__end__"

    class MemorySaver:  # type: ignore[no-redef]
        """In-session checkpoint saver compatible with LangGraph MemorySaver API."""

        def __init__(self) -> None:
            self.storage: dict[str, list[dict[str, Any]]] = {}

        def save(self, thread_id: str, state: dict[str, Any]) -> None:
            self.storage.setdefault(thread_id, []).append(dict(state))

        def get_latest(self, thread_id: str) -> dict[str, Any] | None:
            history = self.storage.get(thread_id, [])
            return history[-1] if history else None


class CompiledStateGraphRunner:
    """Deterministic LangGraph-compatible StateGraph runner with MemorySaver checkpointing."""

    def __init__(
        self,
        nodes: dict[str, Callable[[TradingState], dict[str, Any]]],
        edges: dict[str, str],
        conditional_edges: dict[str, tuple[Callable[[TradingState], str], dict[str, str]]],
        checkpointer: MemorySaver | None = None,
    ) -> None:
        self.nodes = nodes
        self.edges = edges
        self.conditional_edges = conditional_edges
        self.checkpointer = checkpointer or MemorySaver()

    def invoke(self, initial_state: TradingState, config: dict[str, Any] | None = None) -> TradingState:
        thread_id = str((config or {}).get("configurable", {}).get("thread_id", "wallex-default-thread"))
        state: dict[str, Any] = dict(initial_state)
        current_node = self.edges.get(START, "market_scanner")

        steps = 0
        while current_node != END and steps < 25:
            steps += 1
            node_fn = self.nodes[current_node]
            delta = node_fn(state)  # type: ignore[arg-type]
            if isinstance(delta, dict):
                state.update(delta)
            if hasattr(self.checkpointer, "save"):
                self.checkpointer.save(thread_id, state)

            if current_node in self.conditional_edges:
                router_fn, route_map = self.conditional_edges[current_node]
                route_key = router_fn(state)  # type: ignore[arg-type]
                current_node = route_map.get(route_key, END)
            else:
                current_node = self.edges.get(current_node, END)

        return state  # type: ignore[return-value]


def route_after_system1(state: TradingState) -> str:
    """Conditional edge router powered by System-1 Laya/Jev/Mizan decision output."""
    gate = state.get("system1_routing_metadata", {}).get("action_gate", "PROCEED_TO_SYSTEM2")
    has_open = bool(state.get("portfolio_status", {}).get("open_positions"))
    if gate == "PROCEED_TO_SYSTEM2" or has_open:
        return "system2_quant_analyst"
    # FAST_HOLD or EMERGENCY_LIQUIDATE bypasses expensive System-2 LLM call and goes straight to RiskGate
    return "deterministic_risk_gate"


def build_trading_graph(
    graph_nodes: TradingGraphNodes | None = None,
    checkpointer: MemorySaver | None = None,
) -> Any:
    """Build and compile the 8-node Hybrid Graph-Harness StateGraph with MemorySaver."""
    nodes_instance = graph_nodes or TradingGraphNodes()
    memory_saver = checkpointer or MemorySaver()

    if HAS_NATIVE_LANGGRAPH:
        builder = StateGraph(TradingState)
        builder.add_node("market_scanner", nodes_instance.market_scanner_node)
        builder.add_node("kronos_and_sentiment", nodes_instance.kronos_and_sentiment_node)
        builder.add_node("system1_regime_router", nodes_instance.system1_regime_router_node)
        builder.add_node("system2_quant_analyst", nodes_instance.system2_quant_analyst_node)
        builder.add_node("deterministic_risk_gate", nodes_instance.deterministic_risk_gate_node)
        builder.add_node("macro_hitl_interrupt", nodes_instance.macro_hitl_interrupt_node)
        builder.add_node("execution_and_logger", nodes_instance.execution_and_logger_node)
        builder.add_node("evaluator_and_compaction", nodes_instance.evaluator_and_compaction_node)

        builder.add_edge(START, "market_scanner")
        builder.add_edge("market_scanner", "kronos_and_sentiment")
        builder.add_edge("kronos_and_sentiment", "system1_regime_router")
        builder.add_conditional_edges(
            "system1_regime_router",
            route_after_system1,
            {
                "system2_quant_analyst": "system2_quant_analyst",
                "deterministic_risk_gate": "deterministic_risk_gate",
            },
        )
        builder.add_edge("system2_quant_analyst", "deterministic_risk_gate")
        builder.add_edge("deterministic_risk_gate", "macro_hitl_interrupt")
        builder.add_edge("macro_hitl_interrupt", "execution_and_logger")
        builder.add_edge("execution_and_logger", "evaluator_and_compaction")
        builder.add_edge("evaluator_and_compaction", END)
        return builder.compile(checkpointer=memory_saver)

    nodes_map = {
        "market_scanner": nodes_instance.market_scanner_node,
        "kronos_and_sentiment": nodes_instance.kronos_and_sentiment_node,
        "system1_regime_router": nodes_instance.system1_regime_router_node,
        "system2_quant_analyst": nodes_instance.system2_quant_analyst_node,
        "deterministic_risk_gate": nodes_instance.deterministic_risk_gate_node,
        "macro_hitl_interrupt": nodes_instance.macro_hitl_interrupt_node,
        "execution_and_logger": nodes_instance.execution_and_logger_node,
        "evaluator_and_compaction": nodes_instance.evaluator_and_compaction_node,
    }
    edges_map = {
        START: "market_scanner",
        "market_scanner": "kronos_and_sentiment",
        "kronos_and_sentiment": "system1_regime_router",
        "system2_quant_analyst": "deterministic_risk_gate",
        "deterministic_risk_gate": "macro_hitl_interrupt",
        "macro_hitl_interrupt": "execution_and_logger",
        "execution_and_logger": "evaluator_and_compaction",
        "evaluator_and_compaction": END,
    }
    cond_map = {
        "system1_regime_router": (
            route_after_system1,
            {
                "system2_quant_analyst": "system2_quant_analyst",
                "deterministic_risk_gate": "deterministic_risk_gate",
            },
        )
    }
    return CompiledStateGraphRunner(
        nodes=nodes_map,
        edges=edges_map,
        conditional_edges=cond_map,
        checkpointer=memory_saver,
    )
