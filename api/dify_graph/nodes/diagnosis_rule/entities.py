from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from dify_graph.entities.base_node_data import BaseNodeData
from dify_graph.enums import BuiltinNodeTypes, NodeType
from dify_graph.utils.condition.entities import SupportedComparisonOperator


class LeafConditionData(BaseModel):
    """A leaf condition in the diagnosis rule condition tree."""

    id: str
    variable_selector: list[str]
    comparison_operator: SupportedComparisonOperator
    value: str | int | float | bool | list[str] | None = None


class ConditionGroupData(BaseModel):
    """A recursive condition group supporting AND/OR/AT_LEAST logic."""

    id: str
    logic: Literal["AND", "OR", "AT_LEAST"] = "AND"
    minimum: int | None = None
    conditions: list[LeafConditionData | ConditionGroupData] = Field(default_factory=list)

    @classmethod
    def _is_group(cls, item: LeafConditionData | ConditionGroupData) -> bool:
        """Check if an item is a nested group (has 'logic' field) vs a leaf condition."""
        return isinstance(item, ConditionGroupData)


class DiagnosisRuleNodeData(BaseNodeData):
    """Diagnosis Rule node data with recursive condition tree."""

    type: NodeType = BuiltinNodeTypes.DIAGNOSIS_RULE

    condition_tree: ConditionGroupData | None = None
    output_fields: list[str] | None = None
