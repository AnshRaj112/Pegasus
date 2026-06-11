import { combineReducers } from '@reduxjs/toolkit';

import dashboardReducer from '../pages/dashboard/Dashboard.reducer';
import validationReducer from '../pages/validation/Validation.reducer';

const rootReducer = combineReducers({
  dashboard: dashboardReducer,
  validation: validationReducer,
});

export default rootReducer;