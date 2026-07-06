import type { FC } from 'react'
import type { DiagnosisRuleNodeType } from './types'
import type { NodePanelProps } from '@/app/components/workflow/types'
import * as React from 'react'
import { useTranslation } from 'react-i18next'
import useConfig from './use-config'
import Field from '@/app/components/workflow/nodes/_base/components/field'
import Split from '@/app/components/workflow/nodes/_base/components/split'

const i18nPrefix = 'nodes.diagnosisRule'

const Panel: FC<NodePanelProps<DiagnosisRuleNodeType>> = ({ id, data }) => {
  const { t } = useTranslation()
  const { readOnly, conditionTree, handleLogicChange, handleAddCondition } = useConfig(id, data)

  return (
    <div className="mt-2">
      <div className="space-y-4 px-4 pb-2">
        <Field
          title={t(`${i18nPrefix}.logicOperator`, { ns: 'workflow' })}
        >
          <select
            className="w-full rounded-md border border-divider-regular bg-components-input-bg-normal px-3 py-1.5 text-text-primary"
            value={conditionTree.logic}
            onChange={e => handleLogicChange(e.target.value as any)}
            disabled={readOnly}
          >
            <option value="AND">AND (全部满足)</option>
            <option value="OR">OR (任一满足)</option>
            <option value="AT_LEAST">AT_LEAST (至少满足N项)</option>
          </select>
        </Field>

        {conditionTree.logic === 'AT_LEAST' && (
          <Field title={t(`${i18nPrefix}.minimum`, { ns: 'workflow' })}>
            <input
              type="number"
              className="w-full rounded-md border border-divider-regular bg-components-input-bg-normal px-3 py-1.5 text-text-primary"
              min={1}
              max={conditionTree.conditions?.length || 10}
              value={conditionTree.minimum || 1}
              onChange={e => handleLogicChange('AT_LEAST', Number(e.target.value))}
              disabled={readOnly}
            />
          </Field>
        )}

        <Split />

        <Field
          title={t(`${i18nPrefix}.conditions`, { ns: 'workflow' })}
          operations={
            !readOnly
              ? (
                <button
                  type="button"
                  className="cursor-pointer rounded-md border-none bg-transparent p-1 select-none hover:bg-state-base-hover"
                  onClick={handleAddCondition}
                >
                  <span className="i-ri-add-line size-4 text-text-tertiary" aria-hidden="true" />
                </button>
              )
              : undefined
          }
        >
          <div className="text-xs text-text-tertiary">
            {conditionTree.conditions?.length || 0} condition(s) configured
          </div>
        </Field>
      </div>
    </div>
  )
}

export default React.memo(Panel)
