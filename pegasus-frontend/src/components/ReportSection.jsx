import React, { useEffect, useMemo, useRef, useState } from 'react'

const PAGE_SIZE = 10

const variantStyles = {
  mismatched: {
    badge: 'bg-amber-100 text-amber-800 ring-1 ring-amber-200',
    accent: 'border-amber-200 bg-amber-50/70',
    title: 'Mismatched values',
    empty: 'No mismatched rows match the current filter.',
  },
  missing_in_target: {
    badge: 'bg-rose-100 text-rose-800 ring-1 ring-rose-200',
    accent: 'border-rose-200 bg-rose-50/70',
    title: 'Missing in target',
    empty: 'No missing rows match the current filter.',
  },
  extra_in_target: {
    badge: 'bg-sky-100 text-sky-800 ring-1 ring-sky-200',
    accent: 'border-sky-200 bg-sky-50/70',
    title: 'Extra in target',
    empty: 'No extra rows match the current filter.',
  },
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function DetailBlock({ title, record, tone }) {
  if (!record || typeof record !== 'object') return null

  const toneClasses =
    tone === 'source'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
      : 'border-rose-200 bg-rose-50 text-rose-900'

  const entries = Object.entries(record)

  return (
    <section className={`rounded-2xl border p-4 ${toneClasses}`}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h5 className="text-sm font-semibold">{title}</h5>
        <span className="rounded-full bg-white/80 px-2 py-1 text-xs font-medium text-slate-600">
          {entries.length} fields
        </span>
      </div>
      <dl className="grid gap-3 sm:grid-cols-2">
        {entries.map(([key, value]) => (
          <div key={key} className="rounded-xl bg-white/80 p-3 shadow-sm ring-1 ring-black/5">
            <dt className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
              {key}
            </dt>
            <dd className="mt-1 break-words text-sm font-medium text-slate-900">
              {formatValue(value)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function RowCard({ row, variant }) {
  const style = variantStyles[variant] ?? variantStyles.mismatched
  const typeLabel =
    variant === 'missing_in_target'
      ? 'Missing in target'
      : variant === 'extra_in_target'
        ? 'Extra in target'
        : 'Mismatched'

  const detail = row.row_detail ?? {}
  const hasSource = detail.source_record && typeof detail.source_record === 'object'
  const hasTarget = detail.target_record && typeof detail.target_record === 'object'

  return (
    <article className={`rounded-3xl border p-5 shadow-sm ${style.accent}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">
            Record
          </p>
          <h4 className="mt-2 text-lg font-semibold text-slate-900">UID {formatValue(row.uid)}</h4>
          <p className="mt-1 text-sm text-slate-600">
            {variant === 'missing_in_target'
              ? 'Present in the source file but absent from the target file.'
              : variant === 'extra_in_target'
                ? 'Present in the target file but absent from the source file.'
                : 'Values differ between source and target for at least one shared column.'}
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-widest ${style.badge}`}>
          {typeLabel}
        </span>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl bg-white/80 p-4 ring-1 ring-black/5">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
            Column
          </p>
          <p className="mt-2 break-words text-sm font-semibold text-slate-900">
            {formatValue(row.column_name)}
          </p>
        </div>
        <div className="rounded-2xl bg-white/80 p-4 ring-1 ring-black/5">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
            Expected (source)
          </p>
          <p className="mt-2 break-words text-sm font-semibold text-emerald-900">
            {formatValue(row.source_value)}
          </p>
        </div>
        <div className="rounded-2xl bg-white/80 p-4 ring-1 ring-black/5">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
            Actual (target)
          </p>
          <p className="mt-2 break-words text-sm font-semibold text-rose-900">
            {formatValue(row.target_value)}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {hasSource ? (
          <DetailBlock title="Source record" record={detail.source_record} tone="source" />
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 p-4 text-sm text-slate-500">
            Source record details are not available.
          </div>
        )}
        {hasTarget ? (
          <DetailBlock title="Target record" record={detail.target_record} tone="target" />
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 p-4 text-sm text-slate-500">
            Target record details are not available.
          </div>
        )}
      </div>
    </article>
  )
}

function Pagination({ page, totalPages, totalItems, pageSize, onPageChange }) {
  if (!totalItems) return null

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-slate-600">
        Showing <span className="font-semibold text-slate-900">{Math.min((page - 1) * pageSize + 1, totalItems)}</span>
        {' '}
        to <span className="font-semibold text-slate-900">{Math.min(page * pageSize, totalItems)}</span>
        {' '}
        of <span className="font-semibold text-slate-900">{totalItems}</span> rows
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Previous
        </button>
        <span className="rounded-xl bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-900">
          Page {page} of {totalPages}
        </span>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  )
}

export function ReportSection({ type, samples = [] }) {
  const [page, setPage] = useState(1)
  const firstRowRef = useRef(null)
  const style = variantStyles[type] ?? variantStyles.mismatched

  const totalPages = Math.max(1, Math.ceil(samples.length / PAGE_SIZE))

  useEffect(() => {
    setPage(1)
  }, [samples, type])

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages)
    }
  }, [page, totalPages])

  const visibleSamples = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return samples.slice(start, start + PAGE_SIZE)
  }, [samples, page])

  useEffect(() => {
    if (!visibleSamples.length) return
    firstRowRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [page, visibleSamples.length])

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Section</p>
          <h3 className="mt-2 text-2xl font-bold text-slate-900">{style.title}</h3>
          <p className="mt-2 max-w-3xl text-sm text-slate-600">
            {type === 'missing_in_target'
              ? 'Records that exist in the source file but were not found in the target file.'
              : type === 'extra_in_target'
                ? 'Records that exist in the target file but were not found in the source file.'
                : 'Records where the same row exists in both files but one or more values differ.'}
          </p>
        </div>
        <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600 ring-1 ring-slate-200">
          <span className="font-semibold text-slate-900">{samples.length}</span> total rows
          <div className="mt-1 text-xs text-slate-500">Showing up to {PAGE_SIZE} rows per page</div>
        </div>
      </div>

      {samples.length ? (
        <div className="mt-5 space-y-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">Active page</p>
              <p className="mt-2 text-2xl font-black text-slate-900">{page}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">Page size</p>
              <p className="mt-2 text-2xl font-black text-slate-900">{PAGE_SIZE}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">Total pages</p>
              <p className="mt-2 text-2xl font-black text-slate-900">{totalPages}</p>
            </div>
          </div>

          {visibleSamples.map((row, index) => (
            <div key={`${row.uid}-${row.mismatch_type}-${row.column_name ?? 'column'}`} ref={index === 0 ? firstRowRef : null}>
              <RowCard row={row} variant={type} />
            </div>
          ))}

          <Pagination
            page={page}
            totalPages={totalPages}
            totalItems={samples.length}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        </div>
      ) : (
        <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center text-sm text-slate-600">
          {style.empty}
        </div>
      )}
    </section>
  )
}

export default ReportSection