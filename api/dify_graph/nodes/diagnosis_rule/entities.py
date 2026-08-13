from __future__ import annotations

from typing import Literal

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
    """Diagnosis Rule node data with recursive condition tree.

    Supports two modes:
    - ``cases``: multi-branch evaluation (if set, ``condition_tree`` is ignored).
    - ``condition_tree``: legacy single-tree evaluation (backward compatible).
    """

    type: NodeType = BuiltinNodeTypes.DIAGNOSIS_RULE

    condition_tree: ConditionGroupData | None = None
    output_fields: list[str] | None = None

    class Case(BaseModel):
        """A single case branch within the node."""

        case_id: str = Field(..., description="Unique identifier for this case")
        logical_operator: Literal["AND", "OR", "AT_LEAST"] = "AND"
        conditions: list[LeafConditionData | ConditionGroupData] = Field(default_factory=list)

    cases: list[Case] | None = Field(
        default=None,
        description="Multiple case branches (if set, condition_tree is ignored)",
    )
