import { Modal } from 'antd'
import { useNavigate } from 'react-router-dom'
import { CloseOutlined } from '@ant-design/icons'

export default function ValidationResultsModal({ visible, result, onClose, elapsedMs }) {
  const navigate = useNavigate()

  const handleViewReport = () => {
    onClose()
    navigate('/report', { state: { result } })
  }

  return (
    <Modal
      title={null}
      open={visible}
      onCancel={onClose}
      footer={null}
      width={800}
      centered
      closeIcon={<CloseOutlined className="text-xl text-slate-600 hover:text-slate-800" />}
      bodyStyle={{
        padding: '2rem',
        borderRadius: '1rem',
      }}
      style={{
        borderRadius: '1rem',
      }}
    >
      <div className="space-y-6">
        <div className="text-center">
          <p className="mb-2 inline-block rounded-md border border-emerald-300 bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-700">
            ✓ Validation Complete
          </p>
          <h2 className="text-3xl font-bold text-emerald-900">Finished</h2>
          <p className="mt-1 text-sm text-slate-600">
            <strong>{(elapsedMs / 1000).toFixed(1)}s</strong> elapsed
          </p>
        </div>

        {result && (
          <>
            <div className="border-t border-slate-200 pt-4">
              <p className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-700">
                Summary
              </p>

              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 p-4">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-slate-600">
                    Fully Match
                  </span>
                  <span className="mt-2 block font-mono text-2xl font-black text-slate-900">
                    {result.summary?.is_match ? '✓' : '✗'}
                  </span>
                </div>
                <div className="rounded-xl bg-gradient-to-br from-blue-50 to-blue-100 p-4">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-blue-700">
                    Source Rows
                  </span>
                  <span className="mt-2 block font-mono text-2xl font-black text-blue-900">
                    {result.summary?.source_row_count ?? '-'}
                  </span>
                </div>
                <div className="rounded-xl bg-gradient-to-br from-cyan-50 to-cyan-100 p-4">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-cyan-700">
                    Target Rows
                  </span>
                  <span className="mt-2 block font-mono text-2xl font-black text-cyan-900">
                    {result.summary?.target_row_count ?? '-'}
                  </span>
                </div>
                <div className="rounded-xl bg-gradient-to-br from-red-50 to-red-100 p-4">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-red-700">
                    Mismatches
                  </span>
                  <span className="mt-2 block font-mono text-2xl font-black text-red-900">
                    {result.summary?.total_mismatch_records ?? '-'}
                  </span>
                </div>
              </div>
            </div>
            <div className="border-t border-slate-200 pt-4">
              <p className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-700">
                Mismatch Details
              </p>
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg bg-orange-50 p-3 border border-orange-200">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-orange-700">
                    Missing in Target
                  </span>
                  <span className="mt-1 block font-mono text-xl font-black text-orange-900">
                    {result.mismatch_counts?.missing_in_target ?? 0}
                  </span>
                </div>
                <div className="rounded-lg bg-purple-50 p-3 border border-purple-200">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-purple-700">
                    Extra in Target
                  </span>
                  <span className="mt-1 block font-mono text-xl font-black text-purple-900">
                    {result.mismatch_counts?.extra_in_target ?? 0}
                  </span>
                </div>
                <div className="rounded-lg bg-rose-50 p-3 border border-rose-200">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-rose-700">
                    Value Mismatch
                  </span>
                  <span className="mt-1 block font-mono text-xl font-black text-rose-900">
                    {result.mismatch_counts?.value_mismatch ?? 0}
                  </span>
                </div>
              </div>
            </div>

            {result.run_id && (
              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200">
                <p className="text-xs text-slate-600">
                  Run ID: <code className="font-mono font-semibold text-slate-800">{result.run_id}</code>
                </p>
              </div>
            )}

            {result.mismatch_samples?.length > 0 && (
              <button
                type="button"
                onClick={handleViewReport}
                className="w-full rounded-lg bg-gradient-to-r from-[#EB4C4C] to-[#d83e3e] px-6 py-3 font-semibold text-white shadow-lg transition duration-200 hover:from-[#d83e3e] hover:to-[#c23030] hover:shadow-xl"
              >
                View Detailed Report →
              </button>
            )}
          </>
        )}
      </div>
    </Modal>
  )
}