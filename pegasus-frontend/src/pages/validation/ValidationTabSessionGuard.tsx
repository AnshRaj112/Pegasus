import React, { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useAppDispatch } from '../../redux/store';
import { validationActions } from './Validation.reducer';
import { clearValidationTabSession } from './validationTabStorage';
import { isValidationsPath } from './validationRoutes';

/** Clears validation wizard state when navigating away from the validation tab. */
export const ValidationTabSessionGuard: React.FC = () => {
  const location = useLocation();
  const dispatch = useAppDispatch();
  const wasOnValidationsRef = useRef(isValidationsPath(location.pathname));

  useEffect(() => {
    const onValidations = isValidationsPath(location.pathname);
    if (wasOnValidationsRef.current && !onValidations) {
      clearValidationTabSession();
      dispatch(validationActions.resetWizard());
    }
    wasOnValidationsRef.current = onValidations;
  }, [location.pathname, dispatch]);

  return null;
};
