export interface MonotonePoint {
  x: number;
  value: number;
}

/**
 * Fritsch-Carlson monotone cubic interpolation.
 * Interpolates in data-value space so the curve never overshoots between
 * adjacent points (e.g. 0 → 14 stays within [0, 14]).
 */
export const monotoneCurvePath = (
  points: MonotonePoint[],
  scaleY: (value: number) => number,
): string => {
  const n = points.length;
  if (n < 2) return '';
  if (n === 2) {
    return `M${points[0].x},${scaleY(points[0].value)} L${points[1].x},${scaleY(points[1].value)}`;
  }

  const dk: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    dk.push((points[i + 1].value - points[i].value) / (points[i + 1].x - points[i].x));
  }

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

  let d = `M${points[0].x},${scaleY(points[0].value)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = points[i + 1].x - points[i].x;
    const cp1x = points[i].x + h / 3;
    const cp1Value = points[i].value + (mk[i] * h) / 3;
    const cp2x = points[i + 1].x - h / 3;
    const cp2Value = points[i + 1].value - (mk[i + 1] * h) / 3;
    d += ` C${cp1x},${scaleY(cp1Value)} ${cp2x},${scaleY(cp2Value)} ${points[i + 1].x},${scaleY(points[i + 1].value)}`;
  }
  return d;
};
