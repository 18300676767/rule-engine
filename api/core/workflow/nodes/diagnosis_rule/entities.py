"""
Diagnosis Rule Node Data Models.

Defines the condition tree structure that supports AND / OR / AT_LEAST
logical operators with recursive nesting, mirroring the condition-schema.json
from the 治疗方案规则配置管理 project.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from dify_graph.entities.base_node_data import BaseNodeData
from dify_graph.enums import BuiltinNodeTypes, NodeType


class LeafCondition(BaseModel):
    """A single leaf condition: field, operator, and expected value.

    Example:
        {"field": "lab.NIHSS", "operator": "<=", "value": 15}
    """

    field: str = Field(..., description="Dot-separated field path, e.g. 'lab.NIHSS' or 'patient.age'")
    operator: str = Field(..., description="Operator: '=', '!=', '>', '>=', '<', '<=', 'BETWEEN', "
                           "'EQUALS', 'NOT_EQUALS', 'IN', 'NOT_IN', 'CONTAINS', 'CONTAINS_ANY', "
                           "'CONTAINS_ALL', 'NOT_CONTAINS'")
    value: Any = Field(..., description="Expected value(s). Can be number, string, boolean, or array.")


class ConditionGroup(BaseModel):
    """A group of conditions combined by a logical operator.

    Supports three logic types:
    - AND: all child conditions must be true
    - OR: at least one child condition must be true
    - AT_LEAST: at least 'minimum' child conditions must be true
    """

    logic: Literal["AND", "OR", "AT_LEAST"] = Field(
        ..., description="Logical operator combining child conditions"
    )
    minimum: int | None = Field(
        default=None,
        description="Minimum number of conditions that must be true (only for AT_LEAST)",
    )
    conditions: list["LeafCondition | ConditionGroup"] = Field(
        default_factory=list,
        description="Child conditions (leaves or nested groups)",
    )


class DiagnosisRuleNodeData(BaseNodeData):
    """Node data for the Diagnosis Rule evaluation node."""

    type: NodeType = BuiltinNodeTypes.DIAGNOSIS_RULE

    title: str = Field(default="Diagnosis Rule", description="Display title of the node")
    desc: str | None = Field(default=None, description="Optional description")

    condition_tree: ConditionGroup = Field(
        default_factory=lambda: ConditionGroup(logic="AND", conditions=[]),
        description="Root of the condition tree",
    )

    class Case(BaseModel):
        """A single case branch within the node."""

        case_id: str = Field(..., description="Unique identifier for this case")
        logical_operator: Literal["AND", "OR", "AT_LEAST"] = "AND"
        conditions: list[LeafCondition | ConditionGroup] = Field(default_factory=list)

    cases: list[Case] | None = Field(
        default=None,
        description="Multiple case branches (if set, condition_tree is ignored)",
    )
