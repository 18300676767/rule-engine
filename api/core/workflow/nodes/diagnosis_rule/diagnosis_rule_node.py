"""
Diagnosis Rule Evaluation Node.

Recursively evaluates a condition tree (AND / OR / AT_LEAST) against variables
from the workflow variable pool. Supports true/false branch routing like IfElse.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from dify_graph.enums import BuiltinNodeTypes, NodeExecutionType, WorkflowNodeExecutionStatus
from dify_graph.node_events import NodeRunResult
from dify_graph.nodes.base.node import Node
from dify_graph.runtime import VariablePool

from .entities import ConditionGroup, DiagnosisRuleNodeData, LeafCondition

logger = logging.getLogger(__name__)


# ============================================================================
# Operator evaluator (ported from OperatorEvaluator.java)
# ============================================================================

def _to_number(value: Any) -> float | None:
    """Convert a value to float for numeric comparison. Returns None on failure."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


def _to_collection(value: Any) -> list | None:
    """Convert a value to a list for collection operations. Returns None if not a list."""
    if isinstance(value, (list, tuple)):
        return list(value)
    return None


def _apply_operator(actual_value: Any, operator: str, expected: Any) -> bool:
    """Evaluate a single leaf condition by applying the operator."""
    if actual_value is None:
        return operator in ("NOT_IN", "NOT_EQUALS", "NOT_CONTAINS")

    match operator:
        # Numeric comparison
        case "=":
            a_num, e_num = _to_number(actual_value), _to_number(expected)
            if a_num is not None and e_num is not None:
                return a_num == e_num
            return str(actual_value) == str(expected)

        case "!=":
            a_num, e_num = _to_number(actual_value), _to_number(expected)
            if a_num is not None and e_num is not None:
                return a_num != e_num
            return str(actual_value) != str(expected)

        case ">":
            a_num, e_num = _to_number(actual_value), _to_number(expected)
            return a_num is not None and e_num is not None and a_num > e_num

        case ">=":
            a_num, e_num = _to_number(actual_value), _to_number(expected)
            return a_num is not None and e_num is not None and a_num >= e_num

        case "<":
            a_num, e_num = _to_number(actual_value), _to_number(expected)
            return a_num is not None and e_num is not None and a_num < e_num

        case "<=":
            a_num, e_num = _to_number(actual_value), _to_number(expected)
            return a_num is not None and e_num is not None and a_num <= e_num

        case "BETWEEN":
            a_num = _to_number(actual_value)
            if a_num is None or not isinstance(expected, (list, tuple)) or len(expected) < 2:
                return False
            low, high = _to_number(expected[0]), _to_number(expected[1])
            return low is not None and high is not None and low <= a_num <= high

        # String comparison
        case "EQUALS":
            if isinstance(expected, bool) and isinstance(actual_value, bool):
                return actual_value == expected
            return str(actual_value) == str(expected)

        case "NOT_EQUALS":
            return str(actual_value) != str(expected)

        # Collection / membership
        case "IN":
            if isinstance(expected, (list, tuple)):
                return any(str(actual_value) == str(e) for e in expected)
            return str(actual_value) == str(expected)

        case "NOT_IN":
            if isinstance(expected, (list, tuple)):
                return all(str(actual_value) != str(e) for e in expected)
            return str(actual_value) != str(expected)

        case "CONTAINS":
            actual_list = _to_collection(actual_value)
            if actual_list is None:
                return str(actual_value) == str(expected)
            return str(expected) in [str(x) for x in actual_list]

        case "CONTAINS_ANY":
            actual_list = _to_collection(actual_value)
            if actual_list is None or not isinstance(expected, (list, tuple)):
                return False
            actual_strs = [str(x) for x in actual_list]
            return any(str(e) in actual_strs for e in expected)

        case "CONTAINS_ALL":
            actual_list = _to_collection(actual_value)
            if actual_list is None or not isinstance(expected, (list, tuple)):
                return False
            actual_strs = [str(x) for x in actual_list]
            return all(str(e) in actual_strs for e in expected)

        case "NOT_CONTAINS":
            actual_list = _to_collection(actual_value)
            if actual_list is None:
                return True
            return str(expected) not in [str(x) for x in actual_list]

        case _:
            logger.warning("Unknown operator '%s'", operator)
            return False


# ============================================================================
# Variable pool resolver
# ============================================================================

def _resolve_variable(variable_pool: VariablePool, variable_selector: list[str]) -> Any:
    """Resolve a variable from the workflow variable pool using [node_id, var_name].

    Returns the native Python value (str, int, float, bool, list, dict, None).
    """
    if not variable_selector or len(variable_selector) < 2:
        return None
    try:
        segment = variable_pool.get(variable_selector)
        if segment is None:
            return None
        return segment.value
    except Exception:
        return None


# ============================================================================
# Condition tree evaluator
# ============================================================================

def _evaluate_condition_group(group: ConditionGroup, variable_pool: VariablePool) -> bool:
    """Recursively evaluate a condition group with AND / OR / AT_LEAST logic.

    Includes early-termination optimization.
    """
    conditions = group.conditions
    if not conditions:
        logger.warning("ConditionGroup has no child conditions, returning False")
        return False

    logic = group.logic.upper()
    total = len(conditions)

    if logic == "AND":
        for child in conditions:
            if not _evaluate_node(child, variable_pool):
                return False
        return True

    if logic == "OR":
        for child in conditions:
            if _evaluate_node(child, variable_pool):
                return True
        return False

    if logic == "AT_LEAST":
        minimum = group.minimum or 1
        true_count = 0
        evaluated = 0
        for child in conditions:
            evaluated += 1
            if _evaluate_node(child, variable_pool):
                true_count += 1
                if true_count >= minimum:
                    return True
            remaining = total - evaluated
            if true_count + remaining < minimum:
                return False
        return true_count >= minimum

    logger.warning("Unknown logic operator '%s'", logic)
    return False


def _evaluate_node(node: LeafCondition | ConditionGroup | dict[str, Any], variable_pool: VariablePool) -> bool:
    """Recursively evaluate a condition node (leaf or group)."""
    if isinstance(node, dict):
        if "logic" in node:
            node = ConditionGroup.model_validate(node)
        elif "variable_selector" in node:
            node = LeafCondition.model_validate(node)
        else:
            return False

    if isinstance(node, ConditionGroup):
        return _evaluate_condition_group(node, variable_pool)

    if isinstance(node, LeafCondition):
        actual = _resolve_variable(variable_pool, node.variable_selector)
        return _apply_operator(actual, node.comparison_operator, node.value)

    return False


# ============================================================================
# Recursive variable selector extraction
# ============================================================================

def _collect_variable_selectors(node: LeafCondition | ConditionGroup | dict[str, Any]) -> list[list[str]]:
    """Recursively collect all variable_selectors from leaf conditions."""
    selectors: list[list[str]] = []
    if isinstance(node, dict):
        if "logic" in node:
            node = ConditionGroup.model_validate(node)
        elif "variable_selector" in node:
            node = LeafCondition.model_validate(node)
        else:
            return selectors

    if isinstance(node, ConditionGroup):
        for child in node.conditions:
            selectors.extend(_collect_variable_selectors(child))
    elif isinstance(node, LeafCondition):
        if node.variable_selector:
            selectors.append(node.variable_selector)
    return selectors


# ============================================================================
# Node class
# ============================================================================

class DiagnosisRuleNode(Node[DiagnosisRuleNodeData]):
    """Workflow node that evaluates a medical diagnosis rule condition tree.

    Uses the workflow variable pool to resolve variables referenced by
    variable_selectors in leaf conditions. Outputs true/false branch routing
    via edge_source_handle (like IfElse).
    """

    node_type = BuiltinNodeTypes.DIAGNOSIS_RULE
    execution_type = NodeExecutionType.BRANCH

    @classmethod
    def version(cls) -> str:
        return "1"

    def _run(self) -> NodeRunResult:
        """Execute the diagnosis rule evaluation."""
        variable_pool: VariablePool = self.graph_runtime_state.variable_pool
        node_data = self.node_data

        try:
            matched = _evaluate_node(node_data.condition_tree, variable_pool)
        except Exception as e:
            logger.exception("DiagnosisRuleNode evaluation failed: %s", e)
            return NodeRunResult(
                status=WorkflowNodeExecutionStatus.FAILED,
                error=str(e),
            )

        selected_branch = "true" if matched else "false"

        return NodeRunResult(
            status=WorkflowNodeExecutionStatus.SUCCEEDED,
            edge_source_handle=selected_branch,
            outputs={
                "matched": matched,
                "details": {
                    "matched": matched,
                    "logic": node_data.condition_tree.logic,
                },
                "selected_branch_id": selected_branch,
            },
        )

    @classmethod
    def _extract_variable_selector_to_variable_mapping(
        cls,
        *,
        graph_config: Mapping[str, Any],
        node_id: str,
        node_data: DiagnosisRuleNodeData,
    ) -> Mapping[str, Sequence[str]]:
        """Extract variable selectors from all leaf conditions in the condition tree.

        Maps internal keys to variable selectors so the variable pool is populated
        with the required variables before this node runs.
        """
        var_mapping: dict[str, list[str]] = {}
        _ = graph_config  # Explicitly mark as unused

        selectors = _collect_variable_selectors(node_data.condition_tree)
        for selector in selectors:
            key = f"{node_id}.#{'.'.join(selector)}#"
            var_mapping[key] = selector

        return var_mapping
