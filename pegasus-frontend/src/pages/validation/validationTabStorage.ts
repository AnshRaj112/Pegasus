import { OverviewProfileCache, ValidationFormState } from './Validation.interface';

const STORAGE_KEY = 'pegasus.validation.tabSession';

export type ValidationTabSession = {
  validationForm: ValidationFormState;
  isStep1Valid: boolean;
  wizardRunId: string | null;
  overviewProfileCache: OverviewProfileCache | null;
};

export const loadValidationTabSession = (): ValidationTabSession | null => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ValidationTabSession;
    if (!parsed?.validationForm) return null;
    return parsed;
  } catch {
    return null;
  }
};

export const saveValidationTabSession = (session: ValidationTabSession) => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Ignore quota / private-mode errors.
  }
};

export const clearValidationTabSession = () => {
  sessionStorage.removeItem(STORAGE_KEY);
};
