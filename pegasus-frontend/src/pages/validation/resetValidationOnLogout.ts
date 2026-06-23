import type { AppDispatch } from '../../redux/store';
import { clearConnectionBrowseCache } from './browseCacheStorage';
import { validationActions } from './Validation.reducer';
import { clearAllActiveSessions } from './validationSessionStorage';
import { clearValidationWizardSession } from './validationWizardStorage';

/** Clear wizard state and browser session data when the admin session ends. */
export const resetValidationOnLogout = (dispatch: AppDispatch) => {
  clearConnectionBrowseCache();
  clearAllActiveSessions();
  clearValidationWizardSession();
  dispatch(validationActions.resetWizard());
};
