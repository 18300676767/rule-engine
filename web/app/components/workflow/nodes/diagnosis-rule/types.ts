import type { CommonNodeType } from '@/app/components/workflow/types'

export type DiagnosisRuleNodeType = CommonNodeType & {
  condition_tree: {
    logic: 'AND' | 'OR' | 'AT_LEAST'
    minimum?: number
    conditions: Array<LeafCondition | ConditionGroup>
  }
  output_fields?: string[]
}

export type LeafCondition = {
  field: string
  operator: string
  value: any
}

export type ConditionGroup = {
  logic: 'AND' | 'OR' | 'AT_LEAST'
  minimum?: number
  conditions: Array<LeafCondition | ConditionGroup>
}
