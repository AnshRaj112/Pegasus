import { monotoneCurvePath, MonotonePoint } from '../../utils/monotoneCurvePath';

const scaleX = (index: number, count: number) => 60 + (index / Math.max(1, count - 1)) * 740;

const sampleBezierValue = (
  v0: number,
  v1: number,
  v2: number,
  v3: number,
  t: number,
): number => {
  const u = 1 - t;
  return u * u * u * v0 + 3 * u * u * t * v1 + 3 * u * t * t * v2 + t * t * t * v3;
};

const getSegmentValues = (values: number[], mk: number[], index: number): [number, number, number, number] => {
  const h = 1; // normalised segment width — only relative tangents matter
  const v0 = values[index];
  const v3 = values[index + 1];
  const v1 = v0 + (mk[index] * h) / 3;
  const v2 = v3 - (mk[index + 1] * h) / 3;
  return [v0, v1, v2, v3];
};

/** Re-derive tangents the same way the path builder does, for overshoot sampling. */
const computeTangents = (values: number[]): number[] => {
  const n = values.length;
  const dk: number[] = [];
  for (let i = 0; i < n - 1; i++) dk.push(values[i + 1] - values[i]);

  const mk: number[] = new Array(n).fill(0);
  mk[0] = dk[0];
  mk[n - 1] = dk[n - 2];
  for (let i = 1; i < n - 1; i++) {
    mk[i] = dk[i - 1] * dk[i] <= 0 ? 0 : (dk[i - 1] + dk[i]) / 2;
  }
  for (let i = 0; i < n - 1; i++) {
    if (Math.abs(dk[i]) < 1e-10) {
      mk[i] = 0;
      mk[i + 1] = 0;
      continue;
    }
    const alpha = mk[i] / dk[i];
    const beta = mk[i + 1] / dk[i];
    const s = alpha * alpha + beta * beta;
    if (s > 9) {
      const tau = 3 / Math.sqrt(s);
      mk[i] = tau * alpha * dk[i];
      mk[i + 1] = tau * beta * dk[i];
    }
  }
  return mk;
};

const assertNoOvershoot = (values: number[]) => {
  const mk = computeTangents(values);
  for (let i = 0; i < values.length - 1; i++) {
    const lo = Math.min(values[i], values[i + 1]);
    const hi = Math.max(values[i], values[i + 1]);
    const [v0, v1, v2, v3] = getSegmentValues(values, mk, i);
    for (let t = 0; t <= 1; t += 0.02) {
      const v = sampleBezierValue(v0, v1, v2, v3, t);
      expect(v).toBeGreaterThanOrEqual(lo - 1e-9);
      expect(v).toBeLessThanOrEqual(hi + 1e-9);
    }
  }
};

describe('monotoneCurvePath', () => {
  it('returns empty string for fewer than 2 points', () => {
    expect(monotoneCurvePath([], (v) => v)).toBe('');
    expect(monotoneCurvePath([{ x: 0, value: 1 }], (v) => v)).toBe('');
  });

  it('returns a straight line for 2 points', () => {
    expect(monotoneCurvePath(
      [{ x: 10, value: 0 }, { x: 20, value: 5 }],
      (v) => 100 - v * 10,
    )).toBe('M10,100 L20,50');
  });

  it('produces a valid SVG path for multiple points', () => {
    const points: MonotonePoint[] = [0, 4, 7, 0, 0, 14, 10, 5].map((value, i) => ({
      x: scaleX(i, 8),
      value,
    }));
    const path = monotoneCurvePath(points, (v) => 300 - (v / 14) * 270);
    expect(path).toMatch(/^M[\d.]+,[\d.]+/);
    expect(path).toContain('C');
  });

  it('never overshoots on steep 0→14 jumps (screenshot scenario)', () => {
    const values = [4, 7, 0, 0, 14, 10, 5];
    assertNoOvershoot(values);
  });

  it('never overshoots when values are all zero', () => {
    assertNoOvershoot([0, 0, 0, 0, 0, 0, 0]);
  });

  it('never overshoots on monotonic increasing data', () => {
    assertNoOvershoot([1, 3, 5, 8, 12, 14]);
  });

  it('never overshoots on monotonic decreasing data', () => {
    assertNoOvershoot([14, 12, 8, 5, 3, 1, 0]);
  });
});
