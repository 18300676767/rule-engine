import type { FC } from 'react'
import type { Node, NodeOutPutVar, ValueSelector, Var } from '@/app/components/workflow/types'
import { RiAddLine, RiDeleteBinLine } from '@remixicon/react'
import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Button from '@/app/components/base/button'
import { VarType } from '@/app/components/workflow/types'
import { comparisonOperatorNotRequireValue, getOperators } from '@/app/components/workflow/nodes/if-else/utils'
import { ComparisonOperator } from '@/app/components/workflow/nodes/if-else/types'
import ConditionOperator from '@/app/components/workflow/nodes/if-else/components/condition-list/condition-operator'
import ConditionVarSelector from '@/app/components/workflow/nodes/if-else/components/condition-list/condition-var-selector'
import BoolValue from '@/app/components/workflow/panel/chat-variable-panel/components/bool-value'
import { cn } from '@/utils/classnames'
import type { ConditionGroup, LeafCondition } from '../types'

// ---- Color coding for logic types ----
const LOGIC_COLORS: Record<string, string> = {
  AND: '#1890ff',
  OR: '#52c41a',
  AT_LEAST: '#463980ff',
}

const LOGIC_OPTIONS = [
  { value: 'AND', label: 'AND (全部满足)' },
  { value: 'OR', label: 'OR (任一满足)' },
  { value: 'AT_LEAST', label: 'AT_LEAST (至少满足N项)' },
] as const

// ---- ConditionItemView: leaf condition ----

type ConditionItemViewProps = {
  condition: LeafCondition
  groupId: string
  readOnly: boolean
  nodesOutputVars: NodeOutPutVar[]
  availableNodes: Node[]
  onUpdate: (groupId: string, conditionId: string, updates: Partial<LeafCondition>) => void
  onRemove: (groupId: string, conditionId: string) => void
}

const ConditionItemView: FC<ConditionItemViewProps> = ({
  condition,
  groupId,
  readOnly,
  nodesOutputVars,
  availableNodes,
  onUpdate,
  onRemove,
}) => {
  const [isHovered, setIsHovered] = useState(false)
  const [varSelectorOpen, setVarSelectorOpen] = useState(false)

  const hasVarSelected = condition.variable_selector && condition.variable_selector.length > 0
  const varType = condition.varType || VarType.string
  const needValue = !comparisonOperatorNotRequireValue(condition.comparison_operator)

  const handleVarChange = useCallback((valueSelector: ValueSelector, varItem: Var) => {
    onUpdate(groupId, condition.id, {
      variable_selector: valueSelector,
      varType: varItem.type,
      comparison_operator: getOperators(varItem.type)[0],
      value: varItem.type === VarType.boolean ? false : '',
    })
    setVarSelectorOpen(false)
  }, [condition.id, groupId, onUpdate])

  const handleOperatorChange = useCallback((operator: ComparisonOperator) => {
    onUpdate(groupId, condition.id, {
      comparison_operator: operator,
      value: comparisonOperatorNotRequireValue(operator) ? null : condition.value,
    })
  }, [condition.id, condition.value, groupId, onUpdate])

  const handleValueChange = useCallback((value: string | boolean) => {
    onUpdate(groupId, condition.id, { value: value as any })
  }, [condition.id, groupId, onUpdate])

  return (
    <div
      className="mb-1.5 flex items-center gap-1 rounded-lg bg-components-input-bg-normal px-1.5 py-1"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Variable selector */}
      <div className="min-w-0 shrink-0">
        {hasVarSelected
          ? (
              <ConditionVarSelector
                open={varSelectorOpen}
                onOpenChange={setVarSelectorOpen}
                valueSelector={condition.variable_selector}
                varType={varType}
                availableNodes={availableNodes}
                nodesOutputVars={nodesOutputVars}
                onChange={handleVarChange}
              />
            )
          : (
              <ConditionVarSelector
                open={varSelectorOpen}
                onOpenChange={setVarSelectorOpen}
                valueSelector={[]}
                varType={VarType.string}
                availableNodes={availableNodes}
                nodesOutputVars={nodesOutputVars}
                onChange={handleVarChange}
              />
            )}
      </div>

      {/* Operator selector */}
      <div className="shrink-0">
        <ConditionOperator
          varType={varType}
          value={condition.comparison_operator}
          onSelect={handleOperatorChange}
          disabled={readOnly || !hasVarSelected}
        />
      </div>

      {/* Value input */}
      {needValue && (
        <div className="min-w-0 grow">
          {varType === VarType.boolean
            ? (
                <BoolValue
                  value={condition.value as boolean ?? false}
                  onChange={handleValueChange as (v: boolean) => void}
                />
              )
            : varType === VarType.number || varType === VarType.integer
              ? (
                  <input
                    type="number"
                    className="block w-full rounded-md border-none bg-transparent px-2 py-1 text-[13px] text-components-input-text-filled outline-none placeholder:text-components-input-text-placeholder"
                    value={(condition.value as number) ?? ''}
                    onChange={e => handleValueChange(e.target.value)}
                    placeholder="输入值"
                    disabled={readOnly}
                  />
                )
              : (
                  <input
                    type="text"
                    className="block w-full rounded-md border-none bg-transparent px-2 py-1 text-[13px] text-components-input-text-filled outline-none placeholder:text-components-input-text-placeholder"
                    value={(condition.value as string) ?? ''}
                    onChange={e => handleValueChange(e.target.value)}
                    placeholder="输入值"
                    disabled={readOnly}
                  />
                )}
        </div>
      )}

      {/* Delete button */}
      {!readOnly && (
        <button
          type="button"
          className={cn(
            'shrink-0 cursor-pointer rounded p-0.5 text-text-tertiary hover:text-text-destructive',
            !isHovered && 'invisible',
          )}
          onClick={() => onRemove(groupId, condition.id)}
        >
          <RiDeleteBinLine className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}

// ---- ConditionGroupView: recursive group ----

type ConditionGroupViewProps = {
  group: ConditionGroup
  isRoot?: boolean
  readOnly: boolean
  nodesOutputVars: NodeOutPutVar[]
  availableNodes: Node[]
  onAddCondition: (groupId: string) => void
  onAddGroup: (parentGroupId: string) => void
  onRemoveCondition: (groupId: string, conditionId: string) => void
  onUpdateCondition: (groupId: string, conditionId: string, updates: Partial<LeafCondition>) => void
  onToggleLogic: (groupId: string, newLogic: 'AND' | 'OR' | 'AT_LEAST') => void
  onSetMinimum: (groupId: string, minimum: number) => void
}

const ConditionGroupView: FC<ConditionGroupViewProps> = ({
  group,
  isRoot = false,
  readOnly,
  nodesOutputVars,
  availableNodes,
  onAddCondition,
  onAddGroup,
  onRemoveCondition,
  onUpdateCondition,
  onToggleLogic,
  onSetMinimum,
}) => {
  const { t } = useTranslation()
  const borderColor = LOGIC_COLORS[group.logic] || LOGIC_COLORS.AND
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div
      className={cn('rounded-lg', !isRoot && 'my-2')}
      style={!isRoot ? { borderLeft: `3px solid ${borderColor}`, paddingLeft: '12px' } : undefined}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Header: logic selector + minimum */}
      <div className="mb-2 flex items-center gap-2">
        <select
          className="rounded-md border-none bg-components-input-bg-normal px-2 py-1 text-xs font-semibold text-text-secondary outline-none"
          value={group.logic}
          onChange={e => onToggleLogic(group.id, e.target.value as 'AND' | 'OR' | 'AT_LEAST')}
          disabled={readOnly}
          style={{ color: borderColor }}
        >
          {LOGIC_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        {group.logic === 'AT_LEAST' && (
          <div className="flex items-center gap-1 text-xs text-text-tertiary">
            <span>至少满足</span>
            <input
              type="number"
              className="w-12 rounded-md border border-divider-regular bg-components-input-bg-normal px-1.5 py-0.5 text-center text-xs text-text-primary outline-none"
              min={1}
              max={group.conditions?.length || 10}
              value={group.minimum || 1}
              onChange={e => onSetMinimum(group.id, Math.max(1, Number(e.target.value)))}
              disabled={readOnly}
            />
            <span>项</span>
          </div>
        )}

        {/* Delete group button (non-root only) */}
        {!isRoot && !readOnly && (
          <button
            type="button"
            className={cn(
              'ml-auto cursor-pointer rounded p-0.5 text-text-tertiary hover:text-text-destructive',
              !isHovered && 'invisible',
            )}
            onClick={() => {
              // The parent will handle removal via onRemoveCondition with the group's id
              // We need to pass the parent's id, but we don't have it here.
              // Instead, we use a trick: the group's own id is passed, and the recursive
              // remove function will find it in the parent's conditions array.
              onRemoveCondition(group.id, group.id)
            }}
          >
            <RiDeleteBinLine className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Child conditions */}
      {group.conditions && group.conditions.length > 0 && (
        <div className="space-y-1">
          {group.conditions.map((child) => {
            if ('logic' in child) {
              // Nested group
              return (
                <ConditionGroupView
                  key={child.id}
                  group={child as ConditionGroup}
                  readOnly={readOnly}
                  nodesOutputVars={nodesOutputVars}
                  availableNodes={availableNodes}
                  onAddCondition={onAddCondition}
                  onAddGroup={onAddGroup}
                  onRemoveCondition={onRemoveCondition}
                  onUpdateCondition={onUpdateCondition}
                  onToggleLogic={onToggleLogic}
                  onSetMinimum={onSetMinimum}
                />
              )
            }
            else {
              // Leaf condition
              return (
                <ConditionItemView
                  key={child.id}
                  condition={child as LeafCondition}
                  groupId={group.id}
                  readOnly={readOnly}
                  nodesOutputVars={nodesOutputVars}
                  availableNodes={availableNodes}
                  onUpdate={onUpdateCondition}
                  onRemove={onRemoveCondition}
                />
              )
            }
          })}
        </div>
      )}

      {/* Add buttons */}
      {!readOnly && (
        <div className="mt-2 flex items-center gap-2">
          <Button
            size="small"
            variant="tertiary"
            onClick={() => onAddCondition(group.id)}
          >
            <RiAddLine className="mr-1 h-3.5 w-3.5" />
            添加条件
          </Button>
          <Button
            size="small"
            variant="tertiary"
            onClick={() => onAddGroup(group.id)}
          >
            <RiAddLine className="mr-1 h-3.5 w-3.5" />
            添加条件组
          </Button>
        </div>
      )}
    </div>
  )
}

export default ConditionGroupView
