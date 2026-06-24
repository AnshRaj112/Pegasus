/** True when a profile or detection label refers to fixed-width layout. */
export const isFixedWidthFormat = (format: string | null | undefined): boolean => {
  if (!format) return false;
  const normalized = format.toLowerCase().replace(/_/g, '-');
  if (normalized === 'fixed-width' || normalized === 'fixedwidth') return true;
  return normalized.includes('fixed-width');
};

export const DATE_FORMAT_OPTIONS = [
  'YYYY-MM-DD',
  'DD/MM/YYYY',
  'MM/DD/YYYY',
  'DD-MM-YYYY',
  'MM-DD-YYYY',
  'DD-MMM-YYYY',
  'DD-MMMM-YYYY',
  'DD MMM YYYY',
  'DD MMMM YYYY',
  'MMM DD YYYY',
  'MMMM DD YYYY',
  'DD.MM.YYYY',
  'YYYY/MM/DD',
] as const;
