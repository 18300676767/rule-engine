import { useCallback, useMemo } from 'react'
import { produce } from 'immer'
import { v4 as uuid4 } from 'uuid'
import { useEdgesInteractions, useNodeDataUpdate, useNodesReadOnly } from '@/app/components/workflow/hooks'
import useAvailableVarList from '@/app/components/workflow/nodes/_base/hooks/use-available-var-list'
import { ComparisonOperator } from '@/app/components/workflow/nodes/if-else/types'
import { branchNameCorrect } from '@/app/components/workflow/nodes/if-else/utils'
import { VarType } from '@/app/components/workflow/types'
import type { CaseItem, ConditionGroup, DiagnosisRuleNodeType, LeafCondition } from './types'

// ---- Recursive helpers (unchanged, operate on ConditionGroup trees) ----

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

// ---- Branch helpers ----

const getTargetBranchesWithNewCase = (targetBranches: Array<{ id: string; name: string }> | undefined, caseId: string) => {
  if (!targetBranches)
    return targetBranches

  const elseCaseIndex = targetBranches.findIndex(branch => branch.id === 'false')
  if (elseCaseIndex < 0)
    return targetBranches

  return branchNameCorrect([
    ...targetBranches.slice(0, elseCaseIndex),
    { id: caseId, name: '' },
    ...targetBranches.slice(elseCaseIndex),
  ])
}

/** Wrap a case's conditions array as a virtual root ConditionGroup for tree operations. */
function caseAsRoot(caseItem: CaseItem): ConditionGroup {
  return {
    id: `__case_root_${caseItem.case_id}`,
    logic: caseItem.logical_operator,
    conditions: caseItem.conditions,
  }
}

/** Write back root conditions into the case. */
function rootToCase(caseItem: CaseItem, root: ConditionGroup): CaseItem {
  return {
    ...caseItem,
    logical_operator: root.logic,
    conditions: root.conditions,
  }
}

// ---- Hook ----

const useConfig = (id: string, payload: DiagnosisRuleNodeType) => {
  const { handleNodeDataUpdateWithSyncDraft } = useNodeDataUpdate()
  const { nodesReadOnly: readOnly } = useNodesReadOnly()
  const { handleEdgeDeleteByDeleteBranch } = useEdgesInteractions()

  const cases: CaseItem[] = useMemo(() => {
    return payload.cases || [{
      case_id: 'true',
      logical_operator: 'AND' as const,
      conditions: [],
    }]
  }, [payload.cases])

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

  // ---- Case management ----

  const handleAddCase = useCallback(() => {
    updateNodeData((draft) => {
      if (!draft.cases)
        draft.cases = []
      const caseId = uuid4()
      draft.cases.push({
        case_id: caseId,
        logical_operator: 'AND',
        conditions: [],
      })
      draft._targetBranches = getTargetBranchesWithNewCase(draft._targetBranches, caseId)
    })
  }, [updateNodeData])

  const handleRemoveCase = useCallback((caseId: string) => {
    handleEdgeDeleteByDeleteBranch(id, caseId)
    updateNodeData((draft) => {
      draft.cases = draft.cases?.filter(item => item.case_id !== caseId)
      if (draft._targetBranches)
        draft._targetBranches = branchNameCorrect(draft._targetBranches.filter(branch => branch.id !== caseId))
    })
  }, [handleEdgeDeleteByDeleteBranch, id, updateNodeData])

  // ---- Condition operations (scoped to a specific case) ----

  const handleAddCondition = useCallback((caseId: string, groupId: string) => {
    updateNodeData((draft) => {
      const targetCase = draft.cases?.find(c => c.case_id === caseId)
      if (!targetCase) return
      const root = caseAsRoot(targetCase)
      const group = findGroupById(root, groupId)
      if (!group) return
      group.conditions.push({
        id: uuid4(),
        variable_selector: [],
        comparison_operator: ComparisonOperator.is,
        varType: VarType.string,
        value: '',
      } as LeafCondition)
      // Write back
      const idx = draft.cases!.findIndex(c => c.case_id === caseId)
      draft.cases![idx] = rootToCase(targetCase, root)
    })
  }, [updateNodeData])

  const handleAddGroup = useCallback((caseId: string, parentGroupId: string) => {
    updateNodeData((draft) => {
      const targetCase = draft.cases?.find(c => c.case_id === caseId)
      if (!targetCase) return
      const root = caseAsRoot(targetCase)
      const parent = findGroupById(root, parentGroupId)
      if (!parent) return
      parent.conditions.push({
        id: uuid4(),
        logic: 'AND',
        conditions: [],
      } as ConditionGroup)
      const idx = draft.cases!.findIndex(c => c.case_id === caseId)
      draft.cases![idx] = rootToCase(targetCase, root)
    })
  }, [updateNodeData])

  const handleRemoveCondition = useCallback((caseId: string, _groupId: string, conditionId: string) => {
    updateNodeData((draft) => {
      const targetCase = draft.cases?.find(c => c.case_id === caseId)
      if (!targetCase) return
      const root = caseAsRoot(targetCase)
      const updatedRoot = removeConditionFromGroup(root, conditionId)
      const idx = draft.cases!.findIndex(c => c.case_id === caseId)
      draft.cases![idx] = rootToCase(targetCase, updatedRoot)
    })
  }, [updateNodeData])

  const handleUpdateCondition = useCallback((caseId: string, _groupId: string, conditionId: string, updates: Partial<LeafCondition>) => {
    updateNodeData((draft) => {
      const targetCase = draft.cases?.find(c => c.case_id === caseId)
      if (!targetCase) return
      const root = caseAsRoot(targetCase)
      const updatedRoot = updateConditionInGroup(root, conditionId, updates)
      const idx = draft.cases!.findIndex(c => c.case_id === caseId)
      draft.cases![idx] = rootToCase(targetCase, updatedRoot)
    })
  }, [updateNodeData])

  const handleToggleLogic = useCallback((caseId: string, groupId: string, newLogic: 'AND' | 'OR' | 'AT_LEAST') => {
    updateNodeData((draft) => {
      const targetCase = draft.cases?.find(c => c.case_id === caseId)
      if (!targetCase) return
      const root = caseAsRoot(targetCase)
      const group = findGroupById(root, groupId)
      if (!group) return
      group.logic = newLogic
      if (newLogic === 'AT_LEAST' && !group.minimum)
        group.minimum = 1
      if (newLogic !== 'AT_LEAST')
        group.minimum = undefined
      const idx = draft.cases!.findIndex(c => c.case_id === caseId)
      draft.cases![idx] = rootToCase(targetCase, root)
    })
  }, [updateNodeData])

  const handleSetMinimum = useCallback((caseId: string, groupId: string, minimum: number) => {
    updateNodeData((draft) => {
      const targetCase = draft.cases?.find(c => c.case_id === caseId)
      if (!targetCase) return
      const root = caseAsRoot(targetCase)
      const group = findGroupById(root, groupId)
      if (!group) return
      group.minimum = minimum
      const idx = draft.cases!.findIndex(c => c.case_id === caseId)
      draft.cases![idx] = rootToCase(targetCase, root)
    })
  }, [updateNodeData])

  return {
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
  }
}

export default useConfig
