import { configureStore } from '@reduxjs/toolkit';
import { type TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
import createSagaMiddleware from 'redux-saga';

import rootReducer from './reducer';
import rootSaga from './saga';
import { validationActions } from '../pages/validation/Validation.reducer';
import { loadValidationTabSession } from '../pages/validation/validationTabStorage';
import { isValidationsPath, parseValidationRoute } from '../pages/validation/validationRoutes';

// Initialize the saga middleware
const sagaMiddleware = createSagaMiddleware();

// Configure the Redux store
export const store = configureStore({
  reducer: rootReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({ thunk: false }).concat(sagaMiddleware),
  devTools: import.meta.env.MODE !== 'production', // Updated for Vite!
});

// Run the root saga
sagaMiddleware.run(rootSaga);

const restoreValidationTabSession = () => {
  if (typeof window === 'undefined' || !isValidationsPath(window.location.pathname)) return;
  const saved = loadValidationTabSession();
  if (!saved) return;

  const { runId } = parseValidationRoute(window.location.pathname);
  if (runId && saved.wizardRunId && runId !== saved.wizardRunId) return;

  store.dispatch(validationActions.restoreTabSession(saved));
};

restoreValidationTabSession();

// Export types for TypeScript support
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

// Export typed hooks for use in components
export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;