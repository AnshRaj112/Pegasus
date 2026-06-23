export const VALIDATIONS_BASE = '/validations';

export const validationOverviewPath = (runId: string) =>
  `${VALIDATIONS_BASE}/overview/${runId}`;

export const validationMappingPath = (runId: string) =>
  `${VALIDATIONS_BASE}/mapping/${runId}`;

export type ValidationWizardStep = 1 | 2 | 3;

export type ParsedValidationRoute = {
  step: ValidationWizardStep;
  runId: string | null;
};

export const parseValidationRoute = (pathname: string): ParsedValidationRoute => {
  const overviewMatch = /^\/validations\/overview\/([^/]+)\/?$/.exec(pathname);
  if (overviewMatch) return { step: 2, runId: overviewMatch[1] };

  const mappingMatch = /^\/validations\/mapping\/([^/]+)\/?$/.exec(pathname);
  if (mappingMatch) return { step: 3, runId: mappingMatch[1] };

  return { step: 1, runId: null };
};

export const isValidationsPath = (pathname: string): boolean =>
  pathname === VALIDATIONS_BASE
  || pathname === `${VALIDATIONS_BASE}/`
  || pathname.startsWith(`${VALIDATIONS_BASE}/`);
