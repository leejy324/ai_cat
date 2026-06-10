import logging

from langgraph.graph import END, StateGraph

from app.modules.m1_content_analysis import m1_content_analysis
from app.modules.m2_uncertainty import m2_uncertainty
from app.modules.m3_memory_retrieval import m3_memory_retrieval
from app.modules.m4_info_extraction import m4_info_extraction
from app.modules.m5_response_generation import m5_response_generation
from app.modules.state import ConversationState

logger = logging.getLogger(__name__)


def route_after_m1(state: ConversationState) -> str:
    """M1之后的条件分支：高风险直接返回安全模板，其他进入M2"""
    if state.get("risk_level") == "high":
        return "safety_response"
    return "m2_uncertainty"


def route_after_m2(state: ConversationState) -> str:
    """M2之后的条件分支：根据不确定度选择路径"""
    uncertainty = state.get("uncertainty_level", 2)
    if uncertainty == 0:
        return "m3_memory_retrieval"  # L0 → M3 → M4 → M5
    elif uncertainty == 1:
        return "m3_memory_retrieval"  # L1 → M3 → M5（跳过M4）
    else:
        return "m5_response_generation"  # L2 → M5（跳过M3/M4）


def route_after_m3(state: ConversationState) -> str:
    """M3之后的条件分支：L0走M4，L1直接走M5"""
    uncertainty = state.get("uncertainty_level", 2)
    if uncertainty == 0:
        return "m4_info_extraction"  # L0 → M4 → M5
    else:
        return "m5_response_generation"  # L1 → M5（跳过M4）


def build_graph():
    """构建LangGraph管道"""
    graph = StateGraph(ConversationState)

    # 添加节点
    graph.add_node("m1_content_analysis", m1_content_analysis)
    graph.add_node("m2_uncertainty", m2_uncertainty)
    graph.add_node("m3_memory_retrieval", m3_memory_retrieval)
    graph.add_node("m4_info_extraction", m4_info_extraction)
    graph.add_node("m5_response_generation", m5_response_generation)

    # 设置入口
    graph.set_entry_point("m1_content_analysis")

    # M1条件分支
    graph.add_conditional_edges(
        "m1_content_analysis",
        route_after_m1,
        {
            "safety_response": END,
            "m2_uncertainty": "m2_uncertainty",
        },
    )

    # M2条件分支
    graph.add_conditional_edges(
        "m2_uncertainty",
        route_after_m2,
        {
            "m3_memory_retrieval": "m3_memory_retrieval",
            "m5_response_generation": "m5_response_generation",
        },
    )

    # M3条件分支
    graph.add_conditional_edges(
        "m3_memory_retrieval",
        route_after_m3,
        {
            "m4_info_extraction": "m4_info_extraction",
            "m5_response_generation": "m5_response_generation",
        },
    )

    # M4 → M5 → END
    graph.add_edge("m4_info_extraction", "m5_response_generation")
    graph.add_edge("m5_response_generation", END)

    return graph.compile()


# 编译后的图实例（模块级别单例）
conversation_graph = build_graph()
