import { BlockEnum } from '@/app/components/workflow/types'
import type { NodeDefault } from '@/app/components/workflow/types'
import type { DiagnosisRuleNodeType } from './types'
import { BlockClassificationEnum } from '@/app/components/workflow/block-selector/types'
import { genNodeMetaData } from '@/app/components/workflow/utils'

const metaData = genNodeMetaData({
  classification: BlockClassificationEnum.Logic,
  sort: 6,
  type: BlockEnum.DiagnosisRule,
})

const DiagnosisRuleDefault: NodeDefault<DiagnosisRuleNodeType> = {
  metaData,
  defaultValue: {
    title: 'Diagnosis Rule',
    desc: '',
    condition_tree: {
      id: 'root',
      logic: 'AND',
      conditions: [],
    },
    cases: [
      { case_id: 'true', logical_operator: 'AND', conditions: [] },
    ],
    output_fields: ['matched', 'details'],
    _targetBranches: [
      { id: 'true', name: 'IF' },
      { id: 'false', name: 'ELSE' },
    ],
  } as unknown as DiagnosisRuleNodeType,
  checkValid(payload: DiagnosisRuleNodeType) {
    const { cases } = payload
    if (!cases || cases.length === 0) {
      // Fall back to condition_tree check for legacy workflows
      if (!payload.condition_tree || !payload.condition_tree.conditions?.length)
        return { isValid: false, errorMessage: 'Please add at least one condition' }
    }
    else {
      for (let i = 0; i < cases.length; i++) {
        if (!cases[i].conditions?.length)
          return { isValid: false, errorMessage: `Please add conditions to ${i === 0 ? 'IF' : 'ELIF'} case ${i + 1}` }
      }
    }
    return { isValid: true }
  },
  getOutputVars() {
    return [
      { variable: 'matched', type: 'boolean' as any },
      { variable: 'details', type: 'object' as any },
      { variable: 'selected_branch_id', type: 'string' as any },
    ]
  },
}

export default DiagnosisRuleDefault
