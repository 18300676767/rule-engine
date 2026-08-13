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
  const cases = data.cases || []
  const casesLength = cases.length

  return (
    <div className="px-3 py-2">
      {
        cases.map((caseItem, index) => {
          // Build a virtual root group to count conditions for this case
          const root: ConditionGroup = {
            id: '__root',
            logic: caseItem.logical_operator,
            conditions: caseItem.conditions,
          }
          const { leaves, groups } = countConditions(root)

          return (
            <div key={caseItem.case_id}>
              <div className="relative flex h-6 items-center px-1">
                <div className="flex w-full items-center justify-between">
                  <div className="text-[10px] font-semibold text-text-tertiary">
                    {casesLength > 1 && `CASE ${index + 1}`}
                  </div>
                  <div className="text-[12px] font-semibold text-text-secondary">
                    {index === 0 ? 'IF' : 'ELIF'}
                  </div>
                </div>
                <NodeSourceHandle
                  {...props}
                  handleId={caseItem.case_id}
                  handleClassName="!top-1/2 !-right-[21px] !-translate-y-1/2"
                />
              </div>
              <div className="mt-0.5 text-[10px] text-text-tertiary">
                {leaves > 0
                  ? `${leaves} condition(s)${groups > 0 ? `, ${groups} group(s)` : ''}`
                  : t(`${i18nPrefix}.noConditions`, { ns: 'workflow' })}
              </div>
            </div>
          )
        })
      }

      {/* ELSE branch (always last) */}
      <div className="relative mt-1.5 flex h-6 items-center justify-between rounded-md bg-workflow-block-parma-bg px-2">
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-state-disabled-bg" />
          <span className="text-xs font-semibold text-text-secondary">ELSE</span>
        </div>
        <NodeSourceHandle
          {...props}
          handleId="false"
          handleClassName="!top-1/2 !-right-[21px] !-translate-y-1/2"
        />
      </div>
    </div>
  )
}

export default React.memo(DiagnosisRuleNode)
