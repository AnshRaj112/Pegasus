import type { ValidationReducerState } from './Validation.interface';

const STORAGE_KEY = 'pegasus.validation.wizardSession';

export type PersistedValidationWizardState = Pick<
  ValidationReducerState,
  'currentStep' | 'isStep1Valid' | 'validationForm' | 'overviewProfileCache'
>;

export const loadValidationWizardSession = (): PersistedValidationWizardState | null => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedValidationWizardState;
    if (!parsed || typeof parsed !== 'object' || !parsed.validationForm) return null;
    return parsed;
  } catch {
    return null;
  }
};

export const saveValidationWizardSession = (state: PersistedValidationWizardState) => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore quota / private-mode errors.
  }
};

export const clearValidationWizardSession = () => {
  sessionStorage.removeItem(STORAGE_KEY);
};
