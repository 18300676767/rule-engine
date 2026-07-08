from collections.abc import Mapping, Sequence
from typing import Any

from dify_graph.enums import BuiltinNodeTypes, NodeExecutionType, WorkflowNodeExecutionStatus
from dify_graph.node_events import NodeRunResult
from dify_graph.nodes.base.node import Node
from dify_graph.nodes.diagnosis_rule.entities import (
    ConditionGroupData,
    DiagnosisRuleNodeData,
    LeafConditionData,
)
from dify_graph.utils.condition.processor import _evaluate_condition


class DiagnosisRuleNode(Node[DiagnosisRuleNodeData]):
    """
    Diagnosis Rule node: evaluates a recursive condition tree with
    AND/OR/AT_LEAST logic and routes to IF (true) or ELSE (false) branch.
    """

    node_type = BuiltinNodeTypes.DIAGNOSIS_RULE
    execution_type = NodeExecutionType.BRANCH

    @classmethod
    def version(cls) -> str:
        return "1"

    def _run(self) -> NodeRunResult:
        node_inputs: dict[str, Any] = {"conditions": []}
        process_data: dict[str, Any] = {"evaluation_details": []}

        condition_tree = self.node_data.condition_tree
        if not condition_tree:
            return NodeRunResult(
                status=WorkflowNodeExecutionStatus.SUCCEEDED,
                edge_source_handle="false",
                inputs=node_inputs,
                process_data=process_data,
                outputs={"matched": False, "details": "No condition tree defined"},
            )

        try:
            result = self._evaluate_group(condition_tree, process_data["evaluation_details"])
        except Exception as e:
            return NodeRunResult(
                status=WorkflowNodeExecutionStatus.FAILED,
                inputs=node_inputs,
                process_data=process_data,
                error=str(e),
            )

        selected_branch = "true" if result else "false"

        return NodeRunResult(
            status=WorkflowNodeExecutionStatus.SUCCEEDED,
            edge_source_handle=selected_branch,
            inputs=node_inputs,
            process_data=process_data,
            outputs={"matched": result},
        )

    def _evaluate_group(
        self,
        group: ConditionGroupData,
        details: list,
    ) -> bool:
        """
        Recursively evaluate a condition group.

        - AND: all children must be true (short-circuit on first false)
        - OR: at least one child must be true (short-circuit on first true)
        - AT_LEAST: at least `minimum` children must be true
        """
        results: list[bool] = []

        for child in group.conditions:
            if isinstance(child, ConditionGroupData):
                # Nested group - recurse
                child_result = self._evaluate_group(child, details)
            elif isinstance(child, LeafConditionData):
                child_result = self._evaluate_leaf(child, details)
            else:
                # Discriminated union: if it has 'logic' field, it's a group
                child_dict = child if isinstance(child, dict) else {}
                if "logic" in child_dict:
                    child_result = self._evaluate_group(
                        ConditionGroupData.model_validate(child_dict), details
                    )
                else:
                    child_result = self._evaluate_leaf(
                        LeafConditionData.model_validate(child_dict), details
                    )

            results.append(child_result)

            # Short-circuit for AND
            if group.logic == "AND" and not child_result:
                details.append({"group_id": group.id, "logic": group.logic, "result": False, "short_circuit": True})
                return False

            # Short-circuit for OR
            if group.logic == "OR" and child_result:
                details.append({"group_id": group.id, "logic": group.logic, "result": True, "short_circuit": True})
                return True

        # Determine final result based on logic type
        if group.logic == "AND":
            final_result = all(results)
        elif group.logic == "OR":
            final_result = any(results)
        elif group.logic == "AT_LEAST":
            minimum = group.minimum or 1
            final_result = sum(results) >= minimum
        else:
            final_result = all(results)

        details.append({
            "group_id": group.id,
            "logic": group.logic,
            "results": results,
            "final_result": final_result,
        })
        return final_result

    def _evaluate_leaf(
        self,
        condition: LeafConditionData,
        details: list,
    ) -> bool:
        """Evaluate a single leaf condition against the variable pool."""
        variable_pool = self.graph_runtime_state.variable_pool
        variable = variable_pool.get(condition.variable_selector)

        if variable is None:
            raise ValueError(f"Variable {condition.variable_selector} not found")

        actual_value = variable.value if variable else None
        expected_value: Any = condition.value

        # Convert template expressions like {{#node.var#}}
        if isinstance(expected_value, str):
            expected_value = variable_pool.convert_template(expected_value).text

        result = _evaluate_condition(
            operator=condition.comparison_operator,
            value=actual_value,
            expected=expected_value,
        )

        details.append({
            "condition_id": condition.id,
            "variable_selector": condition.variable_selector,
            "operator": condition.comparison_operator,
            "actual_value": actual_value,
            "expected_value": expected_value,
            "result": result,
        })
        return result

    @classmethod
    def _extract_variable_selector_to_variable_mapping(
        cls,
        *,
        graph_config: Mapping[str, Any],
        node_id: str,
        node_data: DiagnosisRuleNodeData,
    ) -> Mapping[str, Sequence[str]]:
        """Extract all variable selectors from the condition tree for dependency tracking."""
        mapping: dict[str, list[str]] = {}
        if not node_data.condition_tree:
            return mapping

        def _collect_from_group(group: ConditionGroupData) -> None:
            for child in group.conditions:
                if isinstance(child, ConditionGroupData):
                    _collect_from_group(child)
                elif isinstance(child, LeafConditionData):
                    if child.variable_selector:
                        selector_key = ".".join(str(s) for s in child.variable_selector)
                        key = f"{node_id}.#{selector_key}#"
                        mapping[key] = child.variable_selector
                else:
                    # Handle dict-based conditions from raw data
                    child_dict = child if isinstance(child, dict) else {}
                    if "logic" in child_dict:
                        _collect_from_group(ConditionGroupData.model_validate(child_dict))
                    elif "variable_selector" in child_dict:
                        leaf = LeafConditionData.model_validate(child_dict)
                        if leaf.variable_selector:
                            selector_key = ".".join(str(s) for s in leaf.variable_selector)
                            key = f"{node_id}.#{selector_key}#"
                            mapping[key] = leaf.variable_selector

        _collect_from_group(node_data.condition_tree)
        return mapping
