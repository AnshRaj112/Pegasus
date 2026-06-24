import React, { useEffect, useState } from 'react';
import { InputNumber, Radio, Spin, Tooltip } from 'antd';
import { Api } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';

export type ValidationTestMode = 'litmus' | 'full';

const MODE_OPTIONS: {
  value: ValidationTestMode;
  title: string;
  description: string;
}[] = [
  {
    value: 'litmus',
    title: 'Litmus',
    description:
      'Validates the complete file and reports pass/fail with counts. No mismatch snippets. '
      + 'If source and target row counts differ, validation stops immediately with a failure.',
  },
  {
    value: 'full',
    title: 'Full',
    description:
      'Validates the complete file and stores only a capped sample of mismatches for the snippet view '
      + '(missing, extra, and per-column value mismatches).',
  },
];

export const ValidationModePanel: React.FC = () => {
  const dispatch = useAppDispatch();
  const { testMode, mismatchSnippetLimit } = useAppSelector((s) => s.validation.validationForm);
  const [loading, setLoading] = useState(true);
  const [defaultLimit, setDefaultLimit] = useState(10);
  const [maxLimit, setMaxLimit] = useState(50);

  useEffect(() => {
    let cancelled = false;
    Api.getValidationOptions()
      .then(({ data }) => {
        if (cancelled) return;
        setDefaultLimit(data.mismatch_snippet_limit_default);
        setMaxLimit(data.mismatch_snippet_limit_max);
        if (mismatchSnippetLimit == null) {
          dispatch(validationActions.setValidationForm({
            mismatchSnippetLimit: data.mismatch_snippet_limit_default,
          }));
        }
      })
      .catch(() => {
        if (!cancelled && mismatchSnippetLimit == null) {
          dispatch(validationActions.setValidationForm({ mismatchSnippetLimit: 10 }));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dispatch, mismatchSnippetLimit]);

  if (loading) {
    return (
      <div style={{ padding: '24px 0', textAlign: 'center' }}>
        <Spin size="small" />
      </div>
    );
  }

  return (
    <section
      style={{
        marginTop: '32px',
        padding: '24px',
        borderRadius: '12px',
        border: '1px solid #e5e2e1',
        background: '#faf9f8',
      }}
    >
      <h3 style={{ margin: '0 0 8px', fontSize: '16px', fontWeight: 700, color: '#1a1d24' }}>
        Validation mode
      </h3>
      <p style={{ margin: '0 0 20px', fontSize: '13px', color: '#727786', lineHeight: 1.5 }}>
        Choose how this run validates your files before proceeding.
      </p>

      <Radio.Group
        value={testMode}
        onChange={(e) => dispatch(validationActions.setValidationForm({ testMode: e.target.value }))}
        style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}
      >
        {MODE_OPTIONS.map((opt) => (
          <Radio
            key={opt.value}
            value={opt.value}
            style={{
              alignItems: 'flex-start',
              padding: '16px',
              borderRadius: '8px',
              border: testMode === opt.value ? '2px solid #234B5F' : '1px solid #d9d9d9',
              background: testMode === opt.value ? '#ffffff' : '#f5f4f3',
              margin: 0,
            }}
          >
            <div>
              <div style={{ fontWeight: 700, fontSize: '14px', color: '#1a1d24' }}>{opt.title}</div>
              <div style={{ fontSize: '13px', color: '#727786', marginTop: '4px', maxWidth: '720px' }}>
                {opt.description}
              </div>
            </div>
          </Radio>
        ))}
      </Radio.Group>

      {testMode === 'full' && (
        <div style={{ marginTop: '20px', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#414755' }}>
            Snippet sample size per category / column
          </span>
          <Tooltip title={`Admin default is ${defaultLimit}. You may choose up to ${maxLimit}.`}>
            <InputNumber
              min={1}
              max={maxLimit}
              value={mismatchSnippetLimit ?? defaultLimit}
              onChange={(value) => dispatch(validationActions.setValidationForm({
                mismatchSnippetLimit: typeof value === 'number' ? value : defaultLimit,
              }))}
            />
          </Tooltip>
          <span style={{ fontSize: '12px', color: '#727786' }}>
            Shows up to this many missing, extra, and value-mismatch rows per compared column in snippets.
          </span>
        </div>
      )}
    </section>
  );
};
