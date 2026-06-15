import { combineReducers } from '@reduxjs/toolkit';

import dashboardReducer from '../pages/dashboard/Dashboard.reducer';
import validationReducer from '../pages/validation/Validation.reducer';
import authReducer from '../pages/auth/Auth.reducer';
import adminReducer from '../pages/admin/Admin.reducer';
import historyReducer from '../pages/history/History.reducer';

const rootReducer = combineReducers({
  dashboard: dashboardReducer,
  validation: validationReducer,
  auth: authReducer,
  admin: adminReducer,
  history: historyReducer,
});

export default rootReducer;