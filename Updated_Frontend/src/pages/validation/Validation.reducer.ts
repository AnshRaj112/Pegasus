import { type PayloadAction, createSlice } from '@reduxjs/toolkit';
import { initializeNullState } from '../../shared/constants/common.constant';
import { type ValidationReducerState, type ValidationDataResponse } from './Validation.interface';

export const initialState: ValidationReducerState = {
  currentStep: 1,
  isStep1Valid: true, // ⚡ New guard flag
  validationDataState: initializeNullState,
};

const validationSlice = createSlice({
  name: 'validation',
  initialState,
  reducers: {
    setWizardStep: (state, action: PayloadAction<number>) => ({
      ...state,
      currentStep: action.payload,
    }),
    // ⚡ Action to toggle step eligibility
    setStep1Valid: (state, action: PayloadAction<boolean>) => ({
      ...state,
      isStep1Valid: action.payload,
    }),
    resetWizard: () => initialState,

    submitValidationRequest: (state) => ({
      ...state,
      validationDataState: { ...initializeNullState, isFetching: true },
    }),
    submitValidationSuccess: (state, action: PayloadAction<ValidationDataResponse>) => ({
      ...state,
      validationDataState: { ...initializeNullState, data: action.payload },
    }),
    submitValidationError: (state, action: PayloadAction<string>) => ({
      ...state,
      validationDataState: { ...initializeNullState, error: action.payload },
    }),
  },
});

export const validationActions = { ...validationSlice.actions };
export default validationSlice.reducer;