import type { FC } from 'react'
import type { NodeProps } from 'reactflow'
import type { DiagnosisRuleNodeType } from './types'
import * as React from 'react'
import { useTranslation } from 'react-i18next'

const i18nPrefix = 'nodes.diagnosisRule'

const DiagnosisRuleNode: FC<NodeProps<DiagnosisRuleNodeType>> = (props) => {
  const { data } = props
  const { t } = useTranslation()
  const conditionCount = data.condition_tree?.conditions?.length || 0

  return (
    <div className="px-3 py-2">
      <div className="flex items-center space-x-1">
        <span className="text-xs font-semibold text-text-secondary">
          {t(`${i18nPrefix}.logic_${data.condition_tree?.logic || 'AND'}`, { ns: 'workflow' })}
        </span>
        {data.condition_tree?.logic === 'AT_LEAST' && (
          <span className="text-xs text-text-tertiary">
            (min: {data.condition_tree.minimum || 1})
          </span>
        )}
      </div>
      <div className="mt-1 text-[10px] text-text-tertiary">
        {conditionCount > 0
          ? `${conditionCount} condition(s)`
          : t(`${i18nPrefix}.noConditions`, { ns: 'workflow' })}
      </div>
    </div>
  )
}

export default React.memo(DiagnosisRuleNode)
