import { useEffect, useState } from 'react'

import { api } from '../api'
import { Button, Message, PageHeader, Panel } from '../components'
import { download, rowClick } from '../format'
import type { LogOut } from '../types'

const LEVEL: Record<string, string> = { WARNING: 'text-nd', ERROR: 'text-fail', CRITICAL: 'text-fail' }

export default function Log({ onApiError }: { onApiError: (e: unknown) => void }) {
  const [log, setLog] = useState<LogOut | null>(null)
  const [open, setOpen] = useState<number | null>(null) // rows have no id: the index in this list
  const [error, setError] = useState('')

  useEffect(() => {
    api.log().then(setLog, (e: Error) => {
      setError(e.message)
      onApiError(e)
    })
  }, [onApiError])

  async function csv() {
    setError('')
    try {
      download(await api.logCsv(), 'ilovestock-log.csv')
    } catch (e) {
      setError((e as Error).message)
      onApiError(e)
    }
  }

  const cols = ['Time', 'Level', 'Where', 'Ticker', 'Message']
  return (
    <>
      <PageHeader title="Log" aside={log && `${log.rows.length} entries`}>
        Warnings and errors from analyses, screens and the server, newest first.
      </PageHeader>
      {error && <Message kind="error">{error}</Message>}
      {log && (
        <Panel>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
            <p className="min-w-0 text-sm break-all text-muted">File: {log.path}</p>
            <Button type="button" variant="quiet" disabled={log.rows.length === 0} onClick={csv}>
              Download CSV
            </Button>
          </div>
          {log.rows.length === 0 ? (
            <Message kind="info">No problems logged.</Message>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[600px] text-left text-sm">
                <thead className="text-muted">
                  <tr className="border-b border-line">
                    {cols.map((h) => (
                      <th key={h} className="py-2 pr-4 font-normal">{h}</th>
                    ))}
                  </tr>
                </thead>
                {log.rows.map((r, i) => {
                  const isOpen = open === i
                  return (
                    <tbody key={i} className="border-b border-line/60 last:border-0">
                      <tr onClick={rowClick(() => setOpen(isOpen ? null : i))}
                        className={`cursor-pointer align-top ${isOpen ? 'bg-well' : 'hover:bg-well/60'}`}>
                        <td className="py-3 pr-4 whitespace-nowrap">
                          <button type="button" className="flex items-center gap-2 text-teal-tint hover:text-text"
                            onClick={() => setOpen(isOpen ? null : i)} aria-expanded={isOpen}>
                            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"
                              className={`transition-transform ${isOpen ? 'rotate-90' : ''}`}>
                              <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5" />
                            </svg>
                            {r.time.replace('T', ' ')}
                          </button>
                        </td>
                        <td className={`py-3 pr-4 font-semibold ${LEVEL[r.level] ?? ''}`}>{r.level}</td>
                        <td className="py-3 pr-4 wrap-anywhere text-muted">{r.where.replace(/^ilovestock\./, '')}</td>
                        <td className="py-3 pr-4">{r.ticker}</td>
                        <td className="py-3 wrap-anywhere">{r.message}</td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td colSpan={cols.length} className="pb-4">
                            {r.details ? (
                              // wrapped: a long traceback line would widen the whole table
                              <pre className="rounded-sm bg-well p-4 text-xs leading-relaxed wrap-anywhere whitespace-pre-wrap text-muted">
                                {r.details}
                              </pre>
                            ) : (
                              <p className="text-muted">No technical details.</p>
                            )}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  )
                })}
              </table>
            </div>
          )}
        </Panel>
      )}
    </>
  )
}
