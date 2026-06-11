import { combineReducers } from '@reduxjs/toolkit';

import dashboardReducer from '../pages/dashboard/Dashboard.reducer';
import validationReducer from '../pages/validation/Validation.reducer';
import authReducer from '../pages/auth/Auth.reducer';
import adminReducer from '../pages/admin/Admin.reducer';

const rootReducer = combineReducers({
  dashboard: dashboardReducer,
  validation: validationReducer,
  auth: authReducer,
  admin : adminReducer
});

export default rootReducer;