import { combineReducers } from '@reduxjs/toolkit';

import dashboardReducer from '../pages/dashboard/Dashboard.reducer';
import validationReducer from '../pages/validation/Validation.reducer';
import authReducer from '../pages/auth/Auth.reducer';
import adminReducer from '../pages/admin/Admin.reducer';
import { reportReducer } from '../pages/report/Report.reducer';
import { profileReducer } from '../pages/profile/Profile.reducer';
import  settingReducer  from '../pages/admin/sections/setting/Setting.reducer';

const rootReducer = combineReducers({
  dashboard: dashboardReducer,
  validation: validationReducer,
  auth: authReducer,
  admin: adminReducer,
  report: reportReducer,
  profile: profileReducer,
  setting: settingReducer
});

export default rootReducer;