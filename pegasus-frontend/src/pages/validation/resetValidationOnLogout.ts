import type { AppDispatch } from '../../redux/store';
import { clearConnectionBrowseCache } from './browseCacheStorage';
import { validationActions } from './Validation.reducer';
import { clearAllActiveSessions } from './validationSessionStorage';

/** Clear wizard state and browser session data when the admin session ends. */
export const resetValidationOnLogout = (dispatch: AppDispatch) => {
  clearConnectionBrowseCache();
  clearAllActiveSessions();
  dispatch(validationActions.resetWizard());
};
