import type { CommonNodeType, ValueSelector, VarType } from '@/app/components/workflow/types'
import type { ComparisonOperator } from '@/app/components/workflow/nodes/if-else/types'

export type { ComparisonOperator } from '@/app/components/workflow/nodes/if-else/types'

export type LeafCondition = {
  id: string                          // unique ID for React key
  variable_selector: ValueSelector     // Dify variable selector [nodeId, varName]
  comparison_operator: ComparisonOperator  // reuse IfElse comparison operators
  varType?: VarType                    // resolved variable type
  value: string | number | boolean | string[] | null
}

export type ConditionGroup = {
  id: string                          // unique ID
  logic: 'AND' | 'OR' | 'AT_LEAST'
  minimum?: number
  conditions: Array<LeafCondition | ConditionGroup>  // recursive nesting
}

export type ConditionTreeNode = ConditionGroup  // root is always a ConditionGroup

export type DiagnosisRuleNodeType = CommonNodeType & {
  condition_tree: ConditionTreeNode
  output_fields?: string[]
  _targetBranches?: Array<{ id: string; name: string }>
}
