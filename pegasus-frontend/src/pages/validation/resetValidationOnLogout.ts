import { AppDispatch } from '../../redux/store';
import { clearConnectionBrowseCache } from './browseCacheStorage';
import { validationActions } from './Validation.reducer';
import { clearAllActiveSessions } from './validationSessionStorage';
import { clearValidationTabSession } from './validationTabStorage';

/** Clear wizard state and browser session data when the admin session ends. */
export const resetValidationOnLogout = (dispatch: AppDispatch) => {
  clearConnectionBrowseCache();
  clearAllActiveSessions();
  clearValidationTabSession();
  dispatch(validationActions.resetWizard());
};
