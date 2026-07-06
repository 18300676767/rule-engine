import type { FC } from 'react'
import * as React from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { InputVarType, type InputVar } from '@/app/components/workflow/types'
import { get } from '@/service/base'
import { cn } from '@/utils/classnames'

type DataSourceField = {
  code: string
  name: string
  type: string
  unit?: string
  options?: string[]
}

type DataSourceCategory = {
  key: string
  name: string
  field_count: number
  fields?: DataSourceField[]
}

type Props = {
  onAddVariable: (payload: InputVar) => boolean
  onAddVariables?: (payloads: InputVar[]) => void
  existingVarKeys: string[]
  readOnly?: boolean
}

const DataSourceSelector: FC<Props> = ({ onAddVariable, onAddVariables, existingVarKeys, readOnly }) => {
  const { t } = useTranslation()
  const [categories, setCategories] = useState<DataSourceCategory[]>([])
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set())
  const [loadedFields, setLoadedFields] = useState<Record<string, DataSourceField[]>>({})
  const [selectedFields, setSelectedFields] = useState<Record<string, Set<string>>>({})

  // Fetch catalog on mount
  useEffect(() => {
    get<{ categories: DataSourceCategory[] }>('/system/datasource/catalog')
      .then(data => setCategories(data.categories || []))
      .catch(console.error)
  }, [])

  // Sync selectedFields with existingVarKeys whenever fields are loaded or existingVarKeys changes
  useEffect(() => {
    setSelectedFields(prev => {
      const next = { ...prev }
      let changed = false
      for (const [key, fields] of Object.entries(loadedFields)) {
        const currentSelected = prev[key] || new Set<string>()
        const shouldSelected = new Set(
          fields.filter(f => existingVarKeys.includes(f.code)).map(f => f.code)
        )
        // Merge: keep user's manual selections + add existing var keys
        const merged = new Set([...currentSelected, ...shouldSelected])
        if (merged.size !== currentSelected.size) {
          next[key] = merged
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [loadedFields, existingVarKeys])

  // Toggle category expand and load fields
  const toggleCategory = useCallback(async (key: string) => {
    const newExpanded = new Set(expandedKeys)
    if (newExpanded.has(key)) {
      newExpanded.delete(key)
    } else {
      newExpanded.add(key)
      if (!loadedFields[key]) {
        try {
          const data = await get<{ fields: DataSourceField[] }>(`/system/datasource/${key}/fields`)
          setLoadedFields(prev => ({ ...prev, [key]: data.fields || [] }))
        } catch (e) {
          console.error(e)
        }
      }
    }
    setExpandedKeys(newExpanded)
  }, [expandedKeys, loadedFields])

  // Select/unselect a single field
  const toggleField = useCallback((categoryKey: string, fieldCode: string) => {
    setSelectedFields(prev => {
      const current = new Set(prev[categoryKey] || [])
      if (current.has(fieldCode)) {
        current.delete(fieldCode)
      } else {
        current.add(fieldCode)
      }
      return { ...prev, [categoryKey]: current }
    })
  }, [])

  // Select all fields in a category
  const selectAllInCategory = useCallback((categoryKey: string) => {
    const fields = loadedFields[categoryKey] || []
    setSelectedFields(prev => ({
      ...prev,
      [categoryKey]: new Set(fields.map(f => f.code)),
    }))
  }, [loadedFields])

  // Deselect all in category
  const deselectAllInCategory = useCallback((categoryKey: string) => {
    setSelectedFields(prev => ({
      ...prev,
      [categoryKey]: new Set(),
    }))
  }, [])

  // Add selected fields as variables (batch to avoid stale closure issue)
  const addSelectedFields = useCallback((categoryKey: string) => {
    const fields = loadedFields[categoryKey] || []
    const selected = selectedFields[categoryKey] || new Set()
    const toAdd: InputVar[] = []
    fields.forEach(f => {
      if (selected.has(f.code) && !existingVarKeys.includes(f.code)) {
        const varType = f.type === 'number' ? InputVarType.number
          : f.type === 'boolean' ? InputVarType.checkbox
          : InputVarType.textInput
        toAdd.push({
          variable: f.code,
          label: f.name,
          type: varType,
          required: false,
          max_length: varType === InputVarType.textInput ? 256 : undefined,
          options: f.options,
          unit: f.unit,
        })
      }
    })
    if (toAdd.length > 0 && onAddVariables) {
      onAddVariables(toAdd)
    } else {
      // Fallback: add one by one (only works for single item)
      toAdd.forEach(v => onAddVariable(v))
    }
  }, [loadedFields, selectedFields, existingVarKeys, onAddVariable, onAddVariables])

  const isAllSelected = useCallback((categoryKey: string) => {
    const fields = loadedFields[categoryKey] || []
    if (fields.length === 0) return false
    const selected = selectedFields[categoryKey] || new Set()
    return fields.every(f => selected.has(f.code))
  }, [loadedFields, selectedFields])

  if (categories.length === 0) return null

  return (
    <div className="mt-2 space-y-1">
      <div className="flex items-center px-4">
        <div className="text-xs font-medium text-text-tertiary uppercase tracking-wide">
          {'系统数据源'}
        </div>
      </div>
      <div className="space-y-0.5">
        {categories.map(cat => {
          const isExpanded = expandedKeys.has(cat.key)
          const fields = loadedFields[cat.key] || []
          const selected = selectedFields[cat.key] || new Set()
          const allSel = fields.length > 0 && fields.every(f => selected.has(f.code))

          return (
            <div key={cat.key}>
              <button
                type="button"
                className="flex w-full items-center justify-between px-4 py-1.5 text-left hover:bg-state-base-hover"
                onClick={() => toggleCategory(cat.key)}
              >
                <span className="text-xs text-text-secondary">
                  {cat.name} ({cat.field_count})
                </span>
                <span className={cn('text-xs text-text-quaternary transition-transform', isExpanded && 'rotate-90')}>
                  ▶
                </span>
              </button>

              {isExpanded && fields.length > 0 && (
                <div className="pb-1">
                  <div className="flex items-center gap-2 px-6 py-1">
                    <button
                      type="button"
                      className="text-xs text-text-accent hover:underline"
                      onClick={() => allSel ? deselectAllInCategory(cat.key) : selectAllInCategory(cat.key)}
                    >
                      {allSel ? '取消全选' : '全选'}
                    </button>
                    <button
                      type="button"
                      className="text-xs text-text-accent hover:underline"
                      onClick={() => addSelectedFields(cat.key)}
                    >
                      添加选中
                    </button>
                  </div>
                  <div className="max-h-40 overflow-y-auto">
                    {fields.map(f => (
                      <label
                        key={f.code}
                        className="flex items-center gap-2 px-6 py-0.5 cursor-pointer hover:bg-state-base-hover text-xs text-text-secondary"
                      >
                        <input
                          type="checkbox"
                          className="size-3 rounded"
                          checked={selected.has(f.code)}
                          onChange={() => toggleField(cat.key, f.code)}
                          disabled={existingVarKeys.includes(f.code)}
                        />
                        <span>{f.name}</span>
                        <span className="text-text-quaternary">({f.code})</span>
                        {f.unit && <span className="text-text-quaternary">{f.unit}</span>}
                        {existingVarKeys.includes(f.code) && (
                          <span className="text-text-accent ml-auto">已添加</span>
                        )}
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default React.memo(DataSourceSelector)
