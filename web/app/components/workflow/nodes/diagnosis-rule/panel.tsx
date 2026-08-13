import type { FC } from 'react'
import type { DiagnosisRuleNodeType, ConditionGroup } from './types'
import type { NodePanelProps } from '@/app/components/workflow/types'
import * as React from 'react'
import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { RiAddLine, RiDeleteBinLine } from '@remixicon/react'
import Button from '@/app/components/base/button'
import useConfig from './use-config'
import ConditionGroupView from './components/condition-tree-editor'

const i18nPrefix = 'nodes.diagnosisRule'

const Panel: FC<NodePanelProps<DiagnosisRuleNodeType>> = ({ id, data }) => {
  const { t } = useTranslation()
  const {
    readOnly,
    cases,
    nodesOutputVars,
    availableNodes,
    handleAddCase,
    handleRemoveCase,
    handleAddCondition,
    handleAddGroup,
    handleRemoveCondition,
    handleUpdateCondition,
    handleToggleLogic,
    handleSetMinimum,
  } = useConfig(id, data)

  return (
    <div className="px-4 py-2">
      {cases.map((caseItem, index) => {
        // Build a virtual root group for this case's conditions
        const rootGroup: ConditionGroup = {
          id: `__case_root_${caseItem.case_id}`,
          logic: caseItem.logical_operator,
          conditions: caseItem.conditions,
        }

        // Create scoped callbacks for this case
        const scopedAddCondition = (groupId: string) => handleAddCondition(caseItem.case_id, groupId)
        const scopedAddGroup = (parentGroupId: string) => handleAddGroup(caseItem.case_id, parentGroupId)
        const scopedRemoveCondition = (groupId: string, conditionId: string) => handleRemoveCondition(caseItem.case_id, groupId, conditionId)
        const scopedUpdateCondition = (groupId: string, conditionId: string, updates: any) => handleUpdateCondition(caseItem.case_id, groupId, conditionId, updates)
        const scopedToggleLogic = (groupId: string, newLogic: 'AND' | 'OR' | 'AT_LEAST') => handleToggleLogic(caseItem.case_id, groupId, newLogic)
        const scopedSetMinimum = (groupId: string, minimum: number) => handleSetMinimum(caseItem.case_id, groupId, minimum)

        return (
          <div key={caseItem.case_id} className="mb-2">
            {/* Case header */}
            <div className="mb-1.5 flex items-center justify-between">
              <div className="system-xs-semibold-uppercase text-text-secondary">
                {index === 0
                  ? t('nodes.ifElse.if', { ns: 'workflow' })
                  : `${t('nodes.ifElse.elif', { ns: 'workflow', defaultValue: 'ELIF' })} ${index > 0 ? index : ''}`}
              </div>
              {index > 0 && (
                <Button
                  className="hover:bg-components-button-destructive-ghost-bg-hover hover:text-components-button-destructive-ghost-text"
                  size="small"
                  variant="ghost"
                  disabled={readOnly}
                  onClick={() => handleRemoveCase(caseItem.case_id)}
                >
                  <RiDeleteBinLine className="mr-1 h-3.5 w-3.5" />
                  {t('operation.remove', { ns: 'common' })}
                </Button>
              )}
            </div>

            <ConditionGroupView
              group={rootGroup}
              isRoot
              readOnly={readOnly}
              nodesOutputVars={nodesOutputVars}
              availableNodes={availableNodes}
              onAddCondition={scopedAddCondition}
              onAddGroup={scopedAddGroup}
              onRemoveCondition={scopedRemoveCondition}
              onUpdateCondition={scopedUpdateCondition}
              onToggleLogic={scopedToggleLogic}
              onSetMinimum={scopedSetMinimum}
            />

            {index < cases.length - 1 && (
              <div className="mx-3 my-2 h-px bg-divider-subtle" />
            )}
          </div>
        )
      })}

      {/* Add ELIF button */}
      <div className="px-0 py-2">
        <Button
          className="w-full"
          variant="tertiary"
          onClick={() => handleAddCase()}
          disabled={readOnly}
        >
          <RiAddLine className="mr-1 h-4 w-4" />
          ELIF
        </Button>
      </div>

      <div className="mx-3 my-2 h-px bg-divider-subtle"></div>

      {/* ELSE branch description */}
      <div className="px-4 py-2">
        <div className="system-xs-semibold-uppercase mb-1 text-text-secondary">
          {t('nodes.ifElse.else', { ns: 'workflow' })}
        </div>
        <div className="text-xs font-normal leading-[18px] text-text-tertiary">
          {t(`${i18nPrefix}.elseDescription`, { ns: 'workflow' })}
        </div>
      </div>
    </div>
  )
}

export default React.memo(Panel)
