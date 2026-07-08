import type { FC } from 'react'
import type { DiagnosisRuleNodeType } from './types'
import type { NodePanelProps } from '@/app/components/workflow/types'
import * as React from 'react'
import { useTranslation } from 'react-i18next'
import useConfig from './use-config'
import ConditionGroupView from './components/condition-tree-editor'

const Panel: FC<NodePanelProps<DiagnosisRuleNodeType>> = ({ id, data }) => {
  const { t } = useTranslation()
  const {
    readOnly,
    conditionTree,
    nodesOutputVars,
    availableNodes,
    handleAddCondition,
    handleAddGroup,
    handleRemoveCondition,
    handleUpdateCondition,
    handleToggleLogic,
    handleSetMinimum,
  } = useConfig(id, data)

  return (
    <div className="px-4 py-2">
      <ConditionGroupView
        group={conditionTree}
        isRoot
        readOnly={readOnly}
        nodesOutputVars={nodesOutputVars}
        availableNodes={availableNodes}
        onAddCondition={handleAddCondition}
        onAddGroup={handleAddGroup}
        onRemoveCondition={handleRemoveCondition}
        onUpdateCondition={handleUpdateCondition}
        onToggleLogic={handleToggleLogic}
        onSetMinimum={handleSetMinimum}
      />
    </div>
  )
}

export default React.memo(Panel)
