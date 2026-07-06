import { useCallback } from 'react'
import { produce } from 'immer'
import { useNodeDataUpdate } from '@/app/components/workflow/hooks'
import type { DiagnosisRuleNodeType } from './types'

const useConfig = (id: string, payload: DiagnosisRuleNodeType) => {
  const { handleNodeDataUpdateWithSyncDraft } = useNodeDataUpdate()

  const conditionTree = payload.condition_tree || {
    logic: 'AND' as const,
    conditions: [],
  }

  const updateNodeData = useCallback(
    (updater: (data: DiagnosisRuleNodeType) => void) => {
      const newData = produce(payload, (draft: any) => {
        updater(draft)
      })
      handleNodeDataUpdateWithSyncDraft({ id, data: newData })
    },
    [id, payload, handleNodeDataUpdateWithSyncDraft],
  )

  const handleLogicChange = useCallback(
    (logic: 'AND' | 'OR' | 'AT_LEAST', minimum?: number) => {
      updateNodeData((draft) => {
        draft.condition_tree = {
          ...draft.condition_tree,
          logic,
          ...(logic === 'AT_LEAST' ? { minimum: minimum || 1 } : { minimum: undefined }),
        }
      })
    },
    [updateNodeData],
  )

  const handleAddCondition = useCallback(() => {
    updateNodeData((draft) => {
      if (!draft.condition_tree)
        draft.condition_tree = { logic: 'AND', conditions: [] }

      draft.condition_tree.conditions.push({
        field: '',
        operator: 'EQUALS',
        value: '',
      })
    })
  }, [updateNodeData])

  return {
    readOnly: false,
    conditionTree,
    handleLogicChange,
    handleAddCondition,
  }
}

export default useConfig
