import { BlockEnum } from '@/app/components/workflow/types'
import type { NodeDefault } from '@/app/components/workflow/types'
import type { DiagnosisRuleNodeType } from './types'
import { BlockClassificationEnum } from '@/app/components/workflow/block-selector/types'

const DiagnosisRuleDefault: NodeDefault<DiagnosisRuleNodeType> = {
  metaData: {
    classification: BlockClassificationEnum.Logic,
    sort: 6,
    type: BlockEnum.DiagnosisRule,
    title: 'Diagnosis Rule',
    author: 'medical-team',
    description: 'Evaluate diagnosis rule conditions with AND/OR/AT_LEAST logic',
  },
  defaultValue: {
    title: 'Diagnosis Rule',
    desc: '',
    condition_tree: {
      logic: 'AND',
      conditions: [],
    },
    output_fields: ['matched', 'details'],
  } as unknown as DiagnosisRuleNodeType,
  checkValid(payload: DiagnosisRuleNodeType) {
    if (!payload.condition_tree || !payload.condition_tree.conditions?.length) {
      return { isValid: false, errorMessage: 'Please add at least one condition' }
    }
    return { isValid: true }
  },
  getOutputVars() {
    return [
      { variable: 'matched', type: 'boolean' as any },
      { variable: 'details', type: 'object' as any },
    ]
  },
}

export default DiagnosisRuleDefault
