import { Col, Row, Statistic, Typography } from 'antd'

/**
 * High-level mismatch counts only — rows missing from target, extra in target,
 * and value-level mismatches (one count per differing cell in compared columns).
 */
export function ValidationMismatchCompact({ result }) {
  const counts = result.mismatch_counts ?? {}
  const nMiss = counts.missing_in_target ?? 0
  const nExt = counts.extra_in_target ?? 0
  const nVal = counts.value_mismatch ?? 0

  return (
    <div>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0, marginBottom: 16 }}>
        These numbers come from the full comparison, not only the sample returned for the detailed view.
      </Typography.Paragraph>
      <Row gutter={[16, 24]}>
        <Col xs={24} sm={8}>
          <Statistic
            title="Rows missing from target"
            value={nMiss}
            valueStyle={{ color: nMiss ? '#d97706' : undefined }}
          />
        </Col>
        <Col xs={24} sm={8}>
          <Statistic
            title="Rows extra in target"
            value={nExt}
            valueStyle={{ color: nExt ? '#7c3aed' : undefined }}
          />
        </Col>
        <Col xs={24} sm={8}>
          <Statistic
            title="Mismatched values"
            value={nVal}
            valueStyle={{ color: nVal ? '#2563eb' : undefined }}
          />
        </Col>
      </Row>
      <Typography.Paragraph type="secondary" style={{ marginTop: 20, marginBottom: 0 }}>
        “Mismatched values” counts each differing compared column for a UID that exists in both files (not the number
        of UIDs). Switch to <Typography.Text strong>Detailed</Typography.Text> to see which UIDs and columns differ.
      </Typography.Paragraph>
    </div>
  )
}
