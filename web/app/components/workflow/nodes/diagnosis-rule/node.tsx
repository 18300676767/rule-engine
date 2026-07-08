import type { FC } from 'react'
import type { NodeProps } from 'reactflow'
import type { ConditionGroup, DiagnosisRuleNodeType } from './types'
import * as React from 'react'
import { useTranslation } from 'react-i18next'
import { NodeSourceHandle } from '../_base/components/node-handle'

const i18nPrefix = 'nodes.diagnosisRule'

function countConditions(group: ConditionGroup): { leaves: number; groups: number } {
  let leaves = 0
  let groups = 0
  for (const child of group.conditions) {
    if ('logic' in child) {
      groups++
      const sub = countConditions(child as ConditionGroup)
      leaves += sub.leaves
      groups += sub.groups
    }
    else {
      leaves++
    }
  }
  return { leaves, groups }
}

const DiagnosisRuleNode: FC<NodeProps<DiagnosisRuleNodeType>> = (props) => {
  const { data } = props
  const { t } = useTranslation()
  const tree = data.condition_tree
  const { leaves, groups } = tree ? countConditions(tree) : { leaves: 0, groups: 0 }

  return (
    <div className="px-3 py-2">
      <div className="flex items-center space-x-1">
        <span className="text-xs font-semibold text-text-secondary">
          {t(`${i18nPrefix}.logic_${tree?.logic || 'AND'}`, { ns: 'workflow' })}
        </span>
        {tree?.logic === 'AT_LEAST' && (
          <span className="text-xs text-text-tertiary">
            (min: {tree.minimum || 1})
          </span>
        )}
      </div>
      <div className="mt-1 text-[10px] text-text-tertiary">
        {leaves > 0
          ? `${leaves} condition(s)${groups > 0 ? `, ${groups} group(s)` : ''}`
          : t(`${i18nPrefix}.noConditions`, { ns: 'workflow' })}
      </div>
      <div className="mt-0.5 flex items-center gap-1">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-state-active-bg" />
        <span className="relative text-[10px] text-text-quaternary">
          IF
          <NodeSourceHandle
            {...props}
            handleId="true"
            handleClassName="!top-1/2 !-right-[21px] !-translate-y-1/2"
          />
        </span>
        <span className="mx-0.5 text-[10px] text-text-quaternary">/</span>
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-state-disabled-bg" />
        <span className="relative text-[10px] text-text-quaternary">
          ELSE
          <NodeSourceHandle
            {...props}
            handleId="false"
            handleClassName="!top-1/2 !-right-[21px] !-translate-y-1/2"
          />
        </span>
      </div>
    </div>
  )
}

export default React.memo(DiagnosisRuleNode)
