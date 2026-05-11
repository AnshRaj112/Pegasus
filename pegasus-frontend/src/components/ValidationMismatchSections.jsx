import { Alert, Badge, Collapse, Empty, Space, Table, Tag, Typography } from 'antd'
import { MismatchSampleRows } from './MismatchSampleRows'

function uniqueUids(samples) {
  const out = []
  const seen = new Set()
  for (const r of samples ?? []) {
    const u = r?.uid
    if (u == null || u === '') continue
    const key = String(u)
    if (!seen.has(key)) {
      seen.add(key)
      out.push(key)
    }
  }
  return out
}

/** Lists UIDs from the current sample; warns when full count exceeds sample size. */
function UidRowList({ samples, totalCount, emptyLabel }) {
  const uids = uniqueUids(samples)
  if (!uids.length) {
    return (
      <Typography.Paragraph type="secondary" style={{ marginTop: 0, marginBottom: 16 }}>
        {emptyLabel ?? 'Sample rows did not include UID values; see the tables below.'}
      </Typography.Paragraph>
    )
  }
  const sampleCoversAll = totalCount > 0 && uids.length >= totalCount
  return (
    <div style={{ marginBottom: 16 }}>
      <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
        Row UIDs{sampleCoversAll ? '' : ' (sample)'}
      </Typography.Text>
      <Space size={[8, 8]} wrap>
        {uids.map((uid) => (
          <Tag key={uid} style={{ fontFamily: 'ui-monospace, monospace' }}>
            {uid}
          </Tag>
        ))}
      </Space>
      {!sampleCoversAll && totalCount > uids.length ? (
        <Typography.Paragraph type="secondary" style={{ marginTop: 10, marginBottom: 0 }}>
          Total in full report: <Typography.Text strong>{totalCount}</Typography.Text> — showing{' '}
          <Typography.Text strong>{uids.length}</Typography.Text> distinct UID(s) from this response. Increase{' '}
          <Typography.Text code>PEGASUS_VALIDATION_MISMATCH_SAMPLE_LIMIT</Typography.Text> to load more.
        </Typography.Paragraph>
      ) : null}
    </div>
  )
}

function columnKeyFromSample(row) {
  return row.column_name == null || row.column_name === '' ? '(unknown)' : String(row.column_name)
}

function sectionLabel(title, count) {
  return (
    <Space size="middle">
      <Typography.Text strong>{title}</Typography.Text>
      <Badge
        count={count}
        overflowCount={999_999_999}
        showZero
        color={count > 0 ? undefined : '#bfbfbf'}
      />
    </Space>
  )
}

function uniqueKeysFromSamples(samples) {
  const keys = new Set()
  for (const r of samples) keys.add(columnKeyFromSample(r))
  return [...keys]
}

function buildValueColumnKeys(apiByCol, comparedCols, valSamples) {
  const keys = []
  const seen = new Set()
  const push = (k) => {
    const s = String(k)
    if (!seen.has(s)) {
      seen.add(s)
      keys.push(s)
    }
  }
  for (const c of comparedCols) push(c)
  for (const k of Object.keys(apiByCol).sort((a, b) => a.localeCompare(b))) push(k)
  for (const k of uniqueKeysFromSamples(valSamples).sort((a, b) => a.localeCompare(b))) push(k)
  return keys
}

export function ValidationMismatchSections({ result }) {
  const tableProps = { compact: false, showMismatchTypeColumn: true, defaultExpandAllRows: true }

  const counts = result.mismatch_counts ?? {}
  const groups = result.mismatch_sample_groups ?? {}
  const apiByCol = result.value_mismatch_by_column ?? {}
  const comparedCols = result.compared_columns ?? []

  const nMiss = counts.missing_in_target ?? 0
  const nExt = counts.extra_in_target ?? 0
  const nVal = counts.value_mismatch ?? 0

  const missSamples = groups.missing_in_target ?? []
  const extSamples = groups.extra_in_target ?? []
  const valSamples = groups.value_mismatch ?? []

  const valueColumnKeys = nVal === 0 ? [] : buildValueColumnKeys(apiByCol, comparedCols, valSamples)
  const valueCountsPartial = nVal > 0 && Object.keys(apiByCol).length === 0

  function badgeCountForColumn(col) {
    if (apiByCol[col] != null) return apiByCol[col]
    if (valueCountsPartial) return valSamples.filter((r) => columnKeyFromSample(r) === col).length
    return apiByCol[col] ?? 0
  }

  const defaultActive = []
  if (nMiss) defaultActive.push('missing')
  else if (nExt) defaultActive.push('extra')
  else if (nVal) defaultActive.push('value')

  const valueInnerDefault = valueColumnKeys.filter((col) => {
    const c = badgeCountForColumn(col)
    return c > 0 && valSamples.some((r) => columnKeyFromSample(r) === col)
  })

  const valueChildren =
    nVal === 0 ? (
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No value mismatches" />
    ) : valueColumnKeys.length === 0 ? (
      <>
        {valSamples.length === 0 ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="No value-mismatch sample rows in this response"
            description={
              <>
                The API reports <Typography.Text strong>{nVal}</Typography.Text> value-level mismatch(es), but the
                sample list is empty. Refresh the Pegasus API to the latest version (sample limit 0 is upgraded
                automatically), set <Typography.Text code>PEGASUS_VALIDATION_MISMATCH_SAMPLE_LIMIT</Typography.Text>{' '}
                to a positive value, and ensure the gateway returns{' '}
                <Typography.Text code>mismatch_sample_groups</Typography.Text> /{' '}
                <Typography.Text code>compared_columns</Typography.Text> (snake_case) or reload after fixing a proxy
                that strips nested JSON.
              </>
            }
          />
        ) : (
          <>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
              No column keys could be inferred from <Typography.Text code>compared_columns</Typography.Text> or{' '}
              <Typography.Text code>value_mismatch_by_column</Typography.Text>. Showing all value-mismatch sample rows
              in one table.
            </Typography.Paragraph>
            <MismatchSampleRows
              samples={valSamples}
              mismatchType="value_mismatch"
              comparedColumns={comparedCols}
              {...tableProps}
            />
          </>
        )}
      </>
    ) : (
      <>
        {valueCountsPartial ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="Per-column totals are not available from the API"
            description="Badge counts below reflect only rows in the current sample for each column. Upgrade the Pegasus API for full value_mismatch_by_column counts, or raise the sample limit."
          />
        ) : null}
        <Collapse
          bordered
          size="small"
          defaultActiveKey={valueInnerDefault.length ? valueInnerDefault : valueColumnKeys.slice(0, 1)}
          items={valueColumnKeys.map((col) => {
            const colCount = badgeCountForColumn(col)
            const colSamples = valSamples.filter((r) => columnKeyFromSample(r) === col)
            return {
              key: col,
              label: (
                <Space size="middle">
                  <Typography.Text code>{col}</Typography.Text>
                  <Badge
                    count={colCount}
                    overflowCount={999_999_999}
                    title={valueCountsPartial ? 'Rows in this sample for this column' : 'Total mismatches on this column'}
                  />
                </Space>
              ),
              children: (
                <div>
                  {colSamples.length ? (
                    <MismatchSampleRows
                      samples={colSamples}
                      mismatchType="value_mismatch"
                      comparedColumns={comparedCols}
                      {...tableProps}
                    />
                  ) : (
                    <Alert
                      type="info"
                      showIcon
                      message="No rows in this sample for this column"
                      description={
                        valueCountsPartial
                          ? `No sample rows for "${col}" in this response. Try raising PEGASUS_VALIDATION_MISMATCH_SAMPLE_LIMIT (up to 10000) so the server returns more rows.`
                          : `There are ${colCount} value mismatch(es) on "${col}" in the full report, but they were not included in the current sample budget. Raise the sample limit or run again after adjusting data.`
                      }
                    />
                  )}
                </div>
              ),
            }
          })}
        />
      </>
    )

  return (
    <Collapse
      bordered
      defaultActiveKey={defaultActive.length ? defaultActive : ['missing']}
      items={[
        {
          key: 'missing',
          label: sectionLabel('Missing from target', nMiss),
          children: (
            <div>
              <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
                Rows present in the source (expected) file but absent in the target (actual) file for the same UID.
              </Typography.Paragraph>
              {nMiss === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="None" />
              ) : missSamples.length ? (
                <>
                  <UidRowList samples={missSamples} totalCount={nMiss} />
                  <MismatchSampleRows
                    samples={missSamples}
                    mismatchType="missing_in_target"
                    comparedColumns={comparedCols}
                    {...tableProps}
                  />
                </>
              ) : (
                <Alert
                  type="info"
                  showIcon
                  message="No sample rows in this category"
                  description={`There are ${nMiss} missing row(s), but none were included in this response. Set PEGASUS_VALIDATION_MISMATCH_SAMPLE_LIMIT to a positive value (max 10000), or upgrade Pegasus so a limit of 0 is replaced automatically.`}
                />
              )}
            </div>
          ),
        },
        {
          key: 'extra',
          label: sectionLabel('Extra in target', nExt),
          children: (
            <div>
              <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
                Rows present in the target file with no matching UID in the source file.
              </Typography.Paragraph>
              {nExt === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="None" />
              ) : extSamples.length ? (
                <>
                  <UidRowList samples={extSamples} totalCount={nExt} />
                  <MismatchSampleRows
                    samples={extSamples}
                    mismatchType="extra_in_target"
                    comparedColumns={comparedCols}
                    {...tableProps}
                  />
                </>
              ) : (
                <Alert
                  type="info"
                  showIcon
                  message="No sample rows in this category"
                  description={`There are ${nExt} extra row(s), but none were included in this response. Set PEGASUS_VALIDATION_MISMATCH_SAMPLE_LIMIT to a positive value (max 10000), or upgrade Pegasus so a limit of 0 is replaced automatically.`}
                />
              )}
            </div>
          ),
        },
        {
          key: 'value',
          label: sectionLabel('Mismatched values', nVal),
          children: (
            <div>
              <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
                Same UID in both files, but one or more compared columns differ. Totals below are per column (full
                report). Expand a column to see expected vs actual values for each sample row.
              </Typography.Paragraph>
              {nVal > 0 && Object.keys(apiByCol).length > 0 ? (
                <Table
                  size="small"
                  pagination={false}
                  style={{ marginBottom: 16 }}
                  rowKey="column"
                  columns={[
                    {
                      title: 'Column',
                      dataIndex: 'column',
                      key: 'column',
                      render: (c) => <Typography.Text code>{c}</Typography.Text>,
                    },
                    {
                      title: 'Mismatched cells',
                      dataIndex: 'count',
                      key: 'count',
                      width: 160,
                    },
                  ]}
                  dataSource={Object.entries(apiByCol)
                    .map(([column, count]) => ({ column, count }))
                    .sort((a, b) => a.column.localeCompare(b.column))}
                />
              ) : null}
              {valueChildren}
            </div>
          ),
        },
      ]}
    />
  )
}
