"""
Diagnosis Rule Evaluation Node.

Recursively evaluates a condition tree (AND / OR / AT_LEAST) against patient
data from the workflow variable pool. This is a direct Python port of the
JsonRuleParser + OperatorEvaluator from the "治疗方案规则配置管理" demo project.
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
    """Evaluate a single leaf condition by applying the operator.

    Ported from OperatorEvaluator.java with the same 15+ operators.
    """
    if actual_value is None:
        # null safety: null is only "true" for negating operators
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
                return True  # empty list doesn't contain anything
            return str(expected) not in [str(x) for x in actual_list]

        case _:
            logger.warning("Unknown operator '%s' for field", operator)
            return False


# ============================================================================
# Field resolver (ported from FieldResolver.java)
# ============================================================================

def _resolve_field(data: dict[str, Any], field_path: str) -> Any:
    """Resolve a dot-separated field path from a nested data dictionary.

    Example: _resolve_field(data, "lab.NIHSS") -> data["lab"]["NIHSS"]
    """
    parts = field_path.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


# ============================================================================
# Condition tree evaluator (ported from JsonRuleParser.java)
# ============================================================================

def _evaluate_condition_group(group: ConditionGroup, data: dict[str, Any]) -> bool:
    """Recursively evaluate a condition group with AND / OR / AT_LEAST logic.

    Includes early-termination optimization:
    - AND: stops at first False
    - OR: stops at first True
    - AT_LEAST: stops when threshold reached or remaining conditions insufficient
    """
    conditions = group.conditions
    if not conditions:
        logger.warning("ConditionGroup has no child conditions, returning False")
        return False

    logic = group.logic.upper()
    total = len(conditions)

    if logic == "AND":
        for child in conditions:
            if not _evaluate_node(child, data):
                return False
        return True

    if logic == "OR":
        for child in conditions:
            if _evaluate_node(child, data):
                return True
        return False

    if logic == "AT_LEAST":
        minimum = group.minimum or 1
        true_count = 0
        evaluated = 0
        for child in conditions:
            evaluated += 1
            if _evaluate_node(child, data):
                true_count += 1
                if true_count >= minimum:
                    return True
            # Early termination: remaining conditions can't satisfy minimum
            remaining = total - evaluated
            if true_count + remaining < minimum:
                return False
        return true_count >= minimum

    logger.warning("Unknown logic operator '%s'", logic)
    return False


def _evaluate_node(node: LeafCondition | ConditionGroup | dict[str, Any], data: dict[str, Any]) -> bool:
    """Recursively evaluate a condition node (leaf or group).

    Accepts dict representations for JSON-serialized conditions.
    """
    if isinstance(node, dict):
        if "logic" in node:
            node = ConditionGroup.model_validate(node)
        elif "field" in node:
            node = LeafCondition.model_validate(node)
        else:
            return False

    if isinstance(node, ConditionGroup):
        return _evaluate_condition_group(node, data)

    if isinstance(node, LeafCondition):
        actual = _resolve_field(data, node.field)
        return _apply_operator(actual, node.operator, node.value)

    return False


# ============================================================================
# Node class
# ============================================================================

class DiagnosisRuleNode(Node[DiagnosisRuleNodeData]):
    """Workflow node that evaluates a medical diagnosis rule condition tree.

    Reads patient data from the variable pool (populated by the Start node),
    recursively evaluates AND / OR / AT_LEAST conditions, and outputs:
      - matched (bool): whether the condition tree is satisfied
      - details (dict): evaluation trace for transparency
    """

    node_type = BuiltinNodeTypes.DIAGNOSIS_RULE
    execution_type = NodeExecutionType.EXECUTABLE

    @classmethod
    def version(cls) -> str:
        return "1"

    def _run(self) -> NodeRunResult:
        """Execute the diagnosis rule evaluation."""
        variable_pool: VariablePool = self.graph_runtime_state.variable_pool
        node_data = self.node_data

        # 1. Build patient data dict from the variable pool
        patient_data: dict[str, Any] = self._build_patient_data(variable_pool)

        # 2. Evaluate conditions
        try:
            if node_data.cases:
                # Multi-case evaluation (like IfElse)
                return self._evaluate_cases(node_data, patient_data)
            else:
                # Single condition tree evaluation
                return self._evaluate_single(node_data, patient_data)
        except Exception as e:
            logger.exception("DiagnosisRuleNode evaluation failed: %s", e)
            return NodeRunResult(
                status=WorkflowNodeExecutionStatus.FAILED,
                error=str(e),
            )

    def _evaluate_single(self, node_data: DiagnosisRuleNodeData, patient_data: dict[str, Any]) -> NodeRunResult:
        """Evaluate a single condition tree."""
        result = _evaluate_node(node_data.condition_tree, patient_data)

        return NodeRunResult(
            status=WorkflowNodeExecutionStatus.SUCCEEDED,
            outputs={
                "matched": result,
                "details": {
                    "matched": result,
                    "logic": node_data.condition_tree.logic,
                    "patient_data_keys": list(patient_data.keys()),
                },
            },
        )

    def _evaluate_cases(self, node_data: DiagnosisRuleNodeData, patient_data: dict[str, Any]) -> NodeRunResult:
        """Evaluate multiple case branches (first-match wins)."""
        matched_case_id: str | None = None
        details_list: list[dict[str, Any]] = []

        for case in node_data.cases:
            group = ConditionGroup(
                logic=case.logical_operator,
                conditions=case.conditions,
            )
            matched = _evaluate_condition_group(group, patient_data)
            details_list.append({
                "case_id": case.case_id,
                "logic": case.logical_operator,
                "matched": matched,
            })
            if matched:
                matched_case_id = case.case_id
                break

        return NodeRunResult(
            status=WorkflowNodeExecutionStatus.SUCCEEDED,
            outputs={
                "matched": matched_case_id is not None,
                "matched_case_id": matched_case_id,
                "details": details_list,
            },
        )

    @staticmethod
    def _build_patient_data(variable_pool: VariablePool) -> dict[str, Any]:
        """Extract patient data from the workflow variable pool.

        Reads all top-level variables from the Start node and builds a flat
        dictionary for condition evaluation. Supports dot-path resolution
        (e.g., 'lab.NIHSS' resolved from nested dicts).
        """
        patient_data: dict[str, Any] = {}

        # Iterate over all node outputs in the variable pool
        for node_id in variable_pool.get_node_ids():
            node_vars = variable_pool.get_node_variables(node_id)
            if node_vars is None:
                continue
            for var_name, var_value in node_vars.items():
                # Skip system variables
                if var_name.startswith("sys."):
                    continue
                if var_name in patient_data:
                    continue
                patient_data[var_name] = var_value

        return patient_data

    @classmethod
    def _extract_variable_selector_to_variable_mapping(
        cls,
        *,
        graph_config: Mapping[str, Any],
        node_id: str,
        node_data: DiagnosisRuleNodeData,
    ) -> Mapping[str, Sequence[str]]:
        """Extract variable selectors from all leaf conditions in the condition tree.

        Unlike IfElse which uses variable_selectors within conditions, our
        leaf conditions reference variables by field name strings. The actual
        variable resolution happens at runtime via the variable pool.
        """
        return {}
