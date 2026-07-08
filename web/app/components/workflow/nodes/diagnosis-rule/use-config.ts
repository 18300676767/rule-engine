import { useCallback, useMemo } from 'react'
import { produce } from 'immer'
import { v4 as uuid4 } from 'uuid'
import { useNodeDataUpdate, useNodesReadOnly } from '@/app/components/workflow/hooks'
import useAvailableVarList from '@/app/components/workflow/nodes/_base/hooks/use-available-var-list'
import { ComparisonOperator } from '@/app/components/workflow/nodes/if-else/types'
import { VarType } from '@/app/components/workflow/types'
import type { ConditionGroup, DiagnosisRuleNodeType, LeafCondition } from './types'

// ---- Recursive helpers ----

function findGroupById(root: ConditionGroup, id: string): ConditionGroup | null {
  if (root.id === id)
    return root
  for (const child of root.conditions) {
    if ('logic' in child) {
      const found = findGroupById(child as ConditionGroup, id)
      if (found) return found
    }
  }
  return null
}

function removeConditionFromGroup(root: ConditionGroup, conditionId: string): ConditionGroup {
  const idx = root.conditions.findIndex(c => c.id === conditionId)
  if (idx !== -1) {
    return {
      ...root,
      conditions: [
        ...root.conditions.slice(0, idx),
        ...root.conditions.slice(idx + 1),
      ],
    }
  }
  return {
    ...root,
    conditions: root.conditions.map((child) => {
      if ('logic' in child)
        return removeConditionFromGroup(child as ConditionGroup, conditionId)
      return child
    }),
  }
}

function updateConditionInGroup(root: ConditionGroup, conditionId: string, updates: Partial<LeafCondition>): ConditionGroup {
  const idx = root.conditions.findIndex(c => c.id === conditionId)
  if (idx !== -1) {
    const target = root.conditions[idx]
    if ('logic' in target)
      return root
    const updated = { ...target, ...updates } as LeafCondition
    return {
      ...root,
      conditions: [
        ...root.conditions.slice(0, idx),
        updated,
        ...root.conditions.slice(idx + 1),
      ],
    }
  }
  return {
    ...root,
    conditions: root.conditions.map((child) => {
      if ('logic' in child)
        return updateConditionInGroup(child as ConditionGroup, conditionId, updates)
      return child
    }),
  }
}

// ---- Hook ----

const useConfig = (id: string, payload: DiagnosisRuleNodeType) => {
  const { handleNodeDataUpdateWithSyncDraft } = useNodeDataUpdate()
  const { nodesReadOnly: readOnly } = useNodesReadOnly()

  const conditionTree: ConditionGroup = useMemo(() => {
    return payload.condition_tree || {
      id: 'root',
      logic: 'AND' as const,
      conditions: [],
    } as ConditionGroup
  }, [payload.condition_tree])

  const updateNodeData = useCallback(
    (updater: (data: DiagnosisRuleNodeType) => void) => {
      const newData = produce(payload, (draft: any) => {
        updater(draft)
      })
      handleNodeDataUpdateWithSyncDraft({ id, data: newData })
    },
    [id, payload, handleNodeDataUpdateWithSyncDraft],
  )

  // Available variables for the variable selector
  const {
    availableVars: nodesOutputVars,
    availableNodesWithParent: availableNodes,
  } = useAvailableVarList(id, {
    onlyLeafNodeVar: false,
    filterVar: () => true,
  })

  // ---- Operations ----

  const handleAddCondition = useCallback((groupId: string) => {
    updateNodeData((draft) => {
      const group = findGroupById(draft.condition_tree, groupId)
      if (!group) return
      group.conditions.push({
        id: uuid4(),
        variable_selector: [],
        comparison_operator: ComparisonOperator.is,
        varType: VarType.string,
        value: '',
      } as LeafCondition)
    })
  }, [updateNodeData])

  const handleAddGroup = useCallback((parentGroupId: string) => {
    updateNodeData((draft) => {
      const parent = findGroupById(draft.condition_tree, parentGroupId)
      if (!parent) return
      parent.conditions.push({
        id: uuid4(),
        logic: 'AND',
        conditions: [],
      } as ConditionGroup)
    })
  }, [updateNodeData])

  const handleRemoveCondition = useCallback((_groupId: string, conditionId: string) => {
    updateNodeData((draft) => {
      draft.condition_tree = removeConditionFromGroup(draft.condition_tree, conditionId)
    })
  }, [updateNodeData])

  const handleUpdateCondition = useCallback((_groupId: string, conditionId: string, updates: Partial<LeafCondition>) => {
    updateNodeData((draft) => {
      draft.condition_tree = updateConditionInGroup(draft.condition_tree, conditionId, updates)
    })
  }, [updateNodeData])

  const handleToggleLogic = useCallback((groupId: string, newLogic: 'AND' | 'OR' | 'AT_LEAST') => {
    updateNodeData((draft) => {
      const group = findGroupById(draft.condition_tree, groupId)
      if (!group) return
      group.logic = newLogic
      if (newLogic === 'AT_LEAST' && !group.minimum)
        group.minimum = 1
      if (newLogic !== 'AT_LEAST')
        group.minimum = undefined
    })
  }, [updateNodeData])

  const handleSetMinimum = useCallback((groupId: string, minimum: number) => {
    updateNodeData((draft) => {
      const group = findGroupById(draft.condition_tree, groupId)
      if (!group) return
      group.minimum = minimum
    })
  }, [updateNodeData])

  return {
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
  }
}

export default useConfig
