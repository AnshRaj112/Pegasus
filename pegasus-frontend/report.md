# Pegasus Frontend — Codebase Rule Compliance Audit

**Audit date:** 2026-06-27  
**Scope:** `src/` audited against `agent-instructions.md`, `docs/skills/`, `docs/font/`, and `docs/color/`  
**Summary:** 47 distinct violations identified across architecture, Redux/Saga, API layer, styling, fonts/colors, routing, and testing.

---

## Architectural & Routing Violations

### 1. `src/App.tsx`

**Rule Broken:** `agent-instructions.md` §3 and `docs/skills/ui-architecture.instructions.mdc` require `createHashRouter` with lazy-loaded routes. `docs/skills/frontend convention.md` specifies HashRouter.

**Current Code:**
```tsx
import { BrowserRouter } from 'react-router-dom';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthSessionManager />
      <AppRoutes />
    </BrowserRouter>
  );
};
```

**Recommended Fix:**
```tsx
import { RouterProvider } from 'react-router-dom';
import { router } from '~/router/router';

const App = () => <RouterProvider router={router} />;
export default App;
```
Define `router` with `createHashRouter` and `React.lazy()` imports for each route feature in `src/router/router.tsx`.

---

### 2. `src/routes/AppRoutes.tsx`

**Rule Broken:** `docs/skills/ui-architecture.instructions.mdc` — route features must be lazy-loaded; route paths should live in constants (`PATHS`), not inline strings.

**Current Code:**
```tsx
import { Dashboard } from '../pages/dashboard/Dashboard';
import { ValidationWizardView } from '../pages/validation/ValidationWizardView';
// ... all routes eagerly imported

<Route path="/" element={<Dashboard />} />
<Route path="/validations/*" element={<ValidationWizardView />} />
```

**Recommended Fix:**
```tsx
const Dashboard = lazy(() => import('~/pages/dashboard/Dashboard'));
const ValidationWizardView = lazy(() => import('~/pages/validation/ValidationWizardView'));

<Route path={PATHS.DASHBOARD} element={<Suspense fallback={<Spin />}><Dashboard /></Suspense>} />
```

---

### 3. `src/routes/ProtectedRoute.tsx`

**Rule Broken:** `docs/skills/ui-architecture.instructions.mdc` and `docs/skills/react-code-style.instructions.mdc` require `AuthGuard` for protected routes, not a custom `ProtectedRoute`.

**Current Code:**
```tsx
export const ProtectedRoute: React.FC = () => {
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated);
  // ...
  return <Navigate to="/login" replace />;
};
```

**Recommended Fix:** Replace with the documented `AuthGuard` component from `src/components/auth-guard/`, wired to the same auth state checks and route constants.

---

### 4. Missing `src/axios-interceptor.ts`

**Rule Broken:** `agent-instructions.md` §3 and `docs/skills/ui-architecture.instructions.mdc` state axios interceptors must be configured in `src/axios-interceptor.ts` for request IDs, CSRF, deduplication, and 401/403 redirects.

**Current Code:** File does not exist. API calls go through `src/shared/api/Api.ts` and `httpClient.ts` without the documented interceptor module.

**Recommended Fix:** Create `src/axios-interceptor.ts` per `docs/skills/frontend convention.md`, import it once in `src/main.tsx` before the app renders, and centralize auth/CSRF/error handling there.

---

### 5. `src/components/ui/Header.tsx`

**Rule Broken:** `docs/skills/ui-architecture.instructions.mdc` — do not hardcode route strings; use `PATHS` constants.

**Current Code:**
```tsx
<Link to="/" className={getLinkClass('/')}>Dashboard</Link>
<Link to="/validations" className={getLinkClass('/validations')}>Validations</Link>
<Link to="/reports" className={getLinkClass('/reports')}>Reports</Link>
```

**Recommended Fix:**
```tsx
import { PATHS } from '~/router/router.constants';

<Link to={PATHS.DASHBOARD} className={getLinkClass(PATHS.DASHBOARD)}>Dashboard</Link>
```

---

## Redux & Saga Violations

### 6. `src/pages/profile/Profile.reducer.ts`

**Rule Broken:** `docs/skills/redux-and-saga.instructions.mdc` — no switch/case reducers for new features; use `createSlice`. Standard state shape uses `isFetching`, not `isLoading`.

**Current Code:**
```ts
export const profileReducer = (state = initialState, action: any): ProfileState => {
  switch (action.type) {
    case 'FETCH_PROFILE_REQUEST':
      return { ...state, isLoading: true, error: null };
    case 'FETCH_PROFILE_SUCCESS':
      return { ...state, isLoading: false, data: action.payload };
    // ...
  }
};
```

**Recommended Fix:**
```ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { initializeNullState } from '~/shared/constants/common.constant';

const profileSlice = createSlice({
  name: 'profile',
  initialState: { fetchProfileState: initializeNullState },
  reducers: {
    fetchProfileRequest: () => ({ fetchProfileState: { ...initializeNullState, isFetching: true } }),
    fetchProfileSuccess: (_s, a: PayloadAction<ProfileData>) => ({ fetchProfileState: { ...initializeNullState, data: a.payload } }),
    fetchProfileError: (_s, a: PayloadAction<string>) => ({ fetchProfileState: { ...initializeNullState, error: a.payload } }),
  },
});
export default profileSlice.reducer;
```

---

### 7. `src/pages/profile/Profile.saga.ts`

**Rule Broken:** `docs/skills/redux-and-saga.instructions.mdc` — sagas must dispatch slice actions (not string literals), use `AxiosError` branching, and show errors via `notification.error` with `NOTIFICATION_SERVICE_TYPES.ERROR`.

**Current Code:**
```ts
yield put({ type: 'FETCH_PROFILE_SUCCESS', payload: data });
// ...
yield takeLatest('FETCH_PROFILE_REQUEST', handleFetchProfile);
```

**Recommended Fix:**
```ts
import { profileActions } from './Profile.reducer';
import { NOTIFICATION_SERVICE_TYPES } from '~/shared/constants/common.constant';

yield put(profileActions.fetchProfileSuccess(data));
yield takeLatest(profileActions.fetchProfileRequest.type, handleFetchProfile);
```

---

### 8. `src/pages/report/Report.reducer.ts`

**Rule Broken:** `docs/skills/redux-and-saga.instructions.mdc` — async state must follow `{ data, isFetching, error }` contract using `initializeNullState` / `initializeEmptyState`.

**Current Code:**
```ts
const initialState: ReportState = {
  activeTab: 'Active',
  activeReports: [],
  isLoading: false,
  error: null,
};
```

**Recommended Fix:**
```ts
const initialState = {
  activeTab: 'Active' as TabType,
  searchQuery: '',
  fetchReportsState: initializeEmptyState,
};
// Use fetchReportsState.isFetching / .data / .error in reducers
```

---

### 9. `src/pages/report/Report.saga.ts`

**Rule Broken:** `docs/skills/redux-and-saga.instructions.mdc` — saga error paths must use `AxiosError` instanceof check and `notification.error` with `NOTIFICATION_SERVICE_TYPES.ERROR`.

**Current Code:**
```ts
} catch (error: any) {
  yield put(reportActions.fetchReportsFailure(error.message || 'Failed to fetch reports'));
}
```

**Recommended Fix:**
```ts
} catch (error) {
  const errorMessage = getApiErrorMessage(error, 'Failed to fetch reports');
  yield put(reportActions.fetchReportsFailure(errorMessage));
  if (error instanceof AxiosError) {
    notification.error({ message: NOTIFICATION_SERVICE_TYPES.ERROR, description: errorMessage });
  }
}
```

---

### 10. `src/pages/auth/Auth.reducer.ts`

**Rule Broken:** `agent-instructions.md` §6 and `docs/skills/redux-and-saga.instructions.mdc` — standard async state property is `isFetching`, not `isLoading`.

**Current Code:**
```ts
export const initialState: AuthReducerState = {
  isAuthenticated: false,
  user: null,
  isLoading: true,
  error: null,
};
```

**Recommended Fix:** Rename `isLoading` → `isFetching` across `Auth.interface.ts`, reducer, and all selectors (e.g., `ProtectedRoute.tsx`).

---

### 11. `src/pages/admin/Admin.saga.ts`

**Rule Broken:** `docs/skills/react-code-style.instructions.mdc` — use `NOTIFICATION_SERVICE_TYPES` for notification titles, not hardcoded strings.

**Current Code:**
```ts
notification.error({
  message: 'Connection test failed',
  description: getApiErrorMessage(error, 'Could not reach the storage bucket.'),
});
notification.success({ message: 'Storage connection removed' });
```

**Recommended Fix:**
```ts
notification.error({
  message: NOTIFICATION_SERVICE_TYPES.ERROR,
  description: getApiErrorMessage(error, 'Could not reach the storage bucket.'),
});
notification.success({
  message: NOTIFICATION_SERVICE_TYPES.SUCCESS,
  description: 'Storage connection removed',
});
```

---

### 12. `src/pages/admin/sections/setting/Setting.saga.ts`

**Rule Broken:** Same as above — success notification uses hardcoded `'Success'` instead of `NOTIFICATION_SERVICE_TYPES.SUCCESS`.

**Current Code:**
```ts
notification.success({
  message: 'Success',
  description: 'Settings saved successfully.',
});
```

**Recommended Fix:**
```ts
notification.success({
  message: NOTIFICATION_SERVICE_TYPES.SUCCESS,
  description: 'Settings saved successfully.',
});
```

---

### 13. `src/pages/profile/Profile.tsx`

**Rule Broken:** `docs/skills/react-code-style.instructions.mdc` — use typed hooks `useAppDispatch` / `useAppSelector` from `~/redux/store`, not raw `useDispatch`.

**Current Code:**
```tsx
import { useDispatch } from 'react-redux';
const dispatch = useDispatch();
```

**Recommended Fix:**
```tsx
import { useAppDispatch } from '~/redux/store';
const dispatch = useAppDispatch();
```

---

## API Layer Violations (Direct Calls in Components)

### 14. `src/pages/validation/steps/FileSelectionStep.tsx`

**Rule Broken:** `docs/skills/react-code-style.instructions.mdc` and `docs/skills/redux-and-saga.instructions.mdc` — no direct API calls in presentation components; API logic belongs in `*.service.ts`, triggered via sagas.

**Current Code:**
```tsx
import { Api, CloudConnection, CloudBrowseEntry } from '../../../shared/api/Api';
// ...
Api.browseCloud({ ... })
Api.listCloudConnections()
```

**Recommended Fix:** Move calls to `Validation.service.ts`, add `browseCloudRequest` / `listConnectionsRequest` saga handlers, and dispatch from the component via `validationActions`.

---

### 15. `src/pages/validation/steps/ConfigureMappingStep.tsx`

**Rule Broken:** Same — direct `Api` calls in UI component (121 inline `style={{}}` usages also violate styling rules).

**Current Code:**
```tsx
Api.previewFixedWidthLayout({ ... })
Api.previewValidationColumns({ ... })
```

**Recommended Fix:** Extract to `Validation.service.ts` and wire through `Validation.saga.ts` with Request/Success/Error reducers.

---

### 16. `src/pages/validation/steps/MappingOverviewStep.tsx`

**Rule Broken:** Direct `Api.profileCloudFile` and `Api.previewValidationColumns` calls in component.

**Current Code:**
```tsx
Api.profileCloudFile({ cloud: form.sourceCloud, ... })
Api.previewValidationColumns({ ... })
```

**Recommended Fix:** Move to service layer; dispatch saga actions from component.

---

### 17. `src/pages/validation/ValidationWizardView.tsx`

**Rule Broken:** Direct `Api.saveValidationDraft` calls in route-level component.

**Current Code:**
```tsx
const { data } = await Api.saveValidationDraft({ ... });
```

**Recommended Fix:**
```tsx
dispatch(validationActions.saveDraftRequest(payload));
// Handle in Validation.saga.ts → Validation.service.ts
```

---

### 18. `src/pages/report/views/SnippetComparison.tsx`

**Rule Broken:** Direct async API calls inside presentation component.

**Current Code:**
```tsx
const { data: detail } = await Api.getValidationHistoryRun(runId);
const { data: page } = await Api.getValidationMismatches(runId, { limit: FETCH_BATCH, offset });
```

**Recommended Fix:** Add `Report.service.ts` methods and `Report.saga.ts` workers; component selects data from Redux store.

---

### 19. `src/pages/report/views/JsonSnippetComparison.tsx`

**Rule Broken:** Same pattern — `Api.getValidationHistoryRun` and `Api.getValidationMismatches` called directly in component.

**Recommended Fix:** Same as SnippetComparison — service + saga + reducer pattern.

---

### 20. `src/pages/report/views/SnippetViewRouter.tsx`

**Rule Broken:** Direct `Api.getValidationHistoryRun` in component `useEffect`.

**Current Code:**
```tsx
const { data } = await Api.getValidationHistoryRun(runId);
```

**Recommended Fix:** Dispatch saga action; route on resolved format type from store.

---

### 21. `src/pages/dashboard/components/EntityCustomizer.tsx`

**Rule Broken:** Direct `Api.createEntity` call in presentation sub-component.

**Current Code:**
```tsx
await Api.createEntity({ display_name: name });
```

**Recommended Fix:**
```tsx
dispatch(dashboardActions.createEntityRequest({ display_name: name }));
```

---

## Styling Violations

### 22. `src/pages/validation/steps/ConfigureMappingStep.tsx` (121 occurrences)

**Rule Broken:** `docs/skills/css-style-sheet.instructions.mdc` — no inline styles; use co-located `.module.scss` with design tokens. Component also lacks a co-located SCSS module.

**Current Code:**
```tsx
<h2 style={{ fontSize: '24px', fontWeight: 600, color: '#1b1b1c', margin: '0 0 8px 0' }}>
<div style={{ padding: '12px', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: '8px' }}>
```

**Recommended Fix:** Create `ConfigureMappingStep.module.scss`:
```scss
.heading {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0 0 0.5rem 0;
}
.errorBanner {
  padding: 0.75rem;
  background-color: var(--status-fail-bg);
  color: var(--status-fail);
  border-radius: 0.5rem;
}
```

---

### 23. `src/pages/report/views/SnippetComparison.tsx` (61 occurrences)

**Rule Broken:** Extensive inline styles and no co-located `.module.scss` file.

**Current Code:**
```tsx
<div style={{ width, height: '14px', backgroundColor: '#e2e8f0', borderRadius: '4px' }} />
```

**Recommended Fix:** Create `SnippetComparison.module.scss` with skeleton, table, and breadcrumb classes using CSS variables from `src/styles/tokens.css`.

---

### 24. `src/pages/report/views/ExecutionHistory.tsx` (55 occurrences)

**Rule Broken:** Inline styles including hardcoded hover colors; no SCSS module.

**Current Code:**
```tsx
<span onClick={() => navigate('/reports')} style={{ cursor: 'pointer' }}
  onMouseEnter={(e) => { e.currentTarget.style.color = '#234B5F'; }}
  onMouseLeave={(e) => { e.currentTarget.style.color = '#64748b'; }}>
```

**Recommended Fix:**
```scss
.breadcrumbLink {
  cursor: pointer;
  color: var(--on-surface-variant);
  &:hover { color: var(--color-midnight-green); }
}
```

---

### 25. `src/pages/validation/steps/FileSelectionStep.tsx` (86 occurrences)

**Rule Broken:** Inline styles throughout; no co-located SCSS module.

**Recommended Fix:** Create `FileSelectionStep.module.scss`; replace all `style={{}}` with module classes and Bootstrap utilities (`d-flex`, `gap-2`, `p-3`).

---

### 26. `src/pages/admin/sections/ConfigureStoreSubView.tsx` (50 occurrences)

**Rule Broken:** Inline styles in admin section component that already has partial SCSS usage elsewhere in admin module.

**Recommended Fix:** Extend `Admin.module.scss` or create `ConfigureStoreSubView.module.scss`.

---

### 27. `src/pages/test/Test.module.scss`

**Rule Broken:** `docs/skills/css-style-sheet.instructions.mdc` — no new colors in SCSS module files; use variables from shared styles. Hardcoded hex values and `px` units violate conventions.

**Current Code:**
```scss
background-color: #ffffff;
color: #191c1e;
border-bottom: 1px solid #e0e3e5;
border-bottom: 2px solid #053447;
width: 250px;
```

**Recommended Fix:**
```scss
@use 'src/styles/tokens' as *;

.testContainer {
  background-color: var(--surface-container-lowest);
  color: var(--on-surface);
}
.tabBtn--active {
  border-bottom: 0.125rem solid var(--color-midnight-green);
}
```

---

### 28. `src/components/ui/Header.module.scss`

**Rule Broken:** Redefines color and font tokens locally instead of importing from shared palette; uses `Inter` instead of project font standard; uses `px` for spacing/sizing.

**Current Code:**
```scss
:root {
  --font-h2: 'Inter', sans-serif;
  --color-onyx-red: #E06B67;
}
height: 52px;
font-size: 18px;
```

**Recommended Fix:** Remove local `:root` overrides; reference `var(--font-h2)` and palette tokens from `src/styles/tokens.css` only. Convert `px` to `rem`.

---

### 29. `src/styles/tokens.css` and `src/App.css`

**Rule Broken:** `docs/skills/css-style-sheet.instructions.mdc` — no new plain `.css` files; always use `.module.scss`. `agent-instructions.md` §6 requires SCSS Modules.

**Current Code:** Global styles live in `src/styles/tokens.css`, `src/App.css`, and `src/main.tsx` imports `./index.css`.

**Recommended Fix:** Migrate tokens to `src/assets/styles/variables.scss`; import via `@use` in module files. Remove legacy Vite starter styles from `App.css`.

---

### 30. Missing co-located SCSS modules (20 components)

**Rule Broken:** `docs/skills/css-style-sheet.instructions.mdc` — every component with custom styles must have a co-located `.module.scss` file.

**Affected files (no SCSS module import):**
- `src/pages/report/Report.tsx`
- `src/pages/report/step/Active.tsx`, `Completed.tsx`, `Saved.tsx`
- `src/pages/report/views/ExecutionHistory.tsx`, `JsonSnippetComparison.tsx`, `SnippetComparison.tsx`, `SnippetViewRouter.tsx`
- `src/pages/validation/steps/ArchiveValidationStep.tsx`, `ConfigureMappingStep.tsx`, `FileSelectionStep.tsx`, `FixedWidthLayoutPanel.tsx`, `JsonParentMappingStep.tsx`, `MappingOverviewStep.tsx`, `OverviewFilePreview.tsx`, `OverviewJsonPreview.tsx`
- `src/pages/validation/ValidationHistoryNavigation.tsx`, `ValidationTabSessionGuard.tsx`
- `src/pages/auth/AuthSessionManager.tsx`
- `src/pages/dashboard/components/TaskRow.tsx`

**Recommended Fix:** Create co-located `ComponentName.module.scss` for each file and migrate inline styles.

---

## Font & Color Violations

### 31. `src/styles/tokens.css`

**Rule Broken:** `agent-instructions.md` §1 references `docs/font/` (Plus Jakarta Sans). Project uses `Inter` throughout token definitions.

**Current Code:**
```css
--font-h2: 'Inter', sans-serif;
--font-h3: 'Inter', sans-serif;
--font-label-md: 'Inter', sans-serif;
```

**Recommended Fix:**
```css
--font-h2: 'Plus Jakarta Sans', sans-serif;
--font-h3: 'Plus Jakarta Sans', sans-serif;
--font-label-md: 'Plus Jakarta Sans', sans-serif;
```
Ensure font files are loaded per `docs/font/` guidelines.

---

### 32. `src/pages/admin/sections/setting/Setting.module.scss`

**Rule Broken:** Introduces undeclared font `JetBrains Mono` outside approved font guidelines.

**Current Code:**
```scss
font-family: 'JetBrains Mono', monospace;
```

**Recommended Fix:** Use the approved monospace stack from design tokens (e.g., `var(--font-mono, ui-monospace, monospace)`) or document JetBrains Mono in `docs/font/` if intentionally added.

---

### 33. Inline hardcoded colors across TSX files

**Rule Broken:** `agent-instructions.md` §6 and `docs/skills/css-style-sheet.instructions.mdc` — do not introduce colors outside `docs/color/` palette. Inline hex values like `#6366f1`, `#64748b`, `#dc2626` appear throughout validation and report components instead of `--color-midnight-green`, `--status-fail`, etc.

**Current Code (representative, `ConfigureMappingStep.tsx`):**
```tsx
color: showUnmappedOnly ? '#4f46e5' : '#475569'
backgroundColor: showUnmappedOnly ? '#eef2ff' : '#fff'
```

**Recommended Fix:**
```tsx
className={showUnmappedOnly ? styles.filterActive : styles.filterInactive}
```
```scss
.filterActive {
  color: var(--primary);
  background-color: var(--primary-fixed);
}
```

---

## Testing Violations

### 34. All feature modules under `src/pages/`

**Rule Broken:** `docs/skills/unit-tests.instructions.mdc` and `agent-instructions.md` §6 — tests must be co-located in `tests/` folders with `renderWithProviders`, reducer tests, and saga tests.

**Current Code:** Zero `tests/` directories exist anywhere under `src/`. No `*.test.tsx`, `*.reducer.test.ts`, or `*.saga.test.ts` files found.

**Recommended Fix:** For each feature module (`dashboard`, `validation`, `report`, `admin`, `auth`, `profile`, `test`), add:
```
src/pages/<feature>/tests/
├── Feature.test.tsx
├── Feature.reducer.test.ts
├── Feature.saga.test.ts
└── Feature.mockData.ts
```

---

## TypeScript & Convention Violations

### 35. `src/pages/validation/steps/FileSelectionStep.tsx`

**Rule Broken:** `docs/skills/react-code-style.instructions.mdc` — avoid `any`; use proper interfaces.

**Current Code:**
```tsx
modifiedAt: formatDate(entry.updated_at || (entry as any).modified_at),
rawModifiedAt: new Date(entry.updated_at || (entry as any).modified_at || 0).getTime(),
```

**Recommended Fix:** Extend `CloudBrowseEntry` in `Validation.interface.ts` with optional `modified_at?: string` and remove `as any` casts.

---

### 36. `src/pages/validation/ValidationWizardView.tsx`

**Rule Broken:** Avoid `any` for new code.

**Current Code:**
```tsx
const cloudObjectKey = (cloud: any): string =>
```

**Recommended Fix:**
```tsx
const cloudObjectKey = (cloud: GoogleCloudStorageConfig | null): string =>
```

---

### 37. Route-level named exports vs default exports

**Rule Broken:** `docs/skills/react-code-style.instructions.mdc` — prefer default export for route-level and feature components.

**Current Code:** Most route components use named exports:
```tsx
export const ValidationWizardView: React.FC = () => { ... }
export const Dashboard: React.FC = () => { ... }
export const Report: React.FC = () => { ... }
```

**Recommended Fix:**
```tsx
const ValidationWizardView: React.FC = () => { ... }
export default ValidationWizardView;
```

---

### 38. `src/shared/constants/common.constant.ts`

**Rule Broken:** `docs/skills/frontend convention.md` references `common.constants.ts` (plural). Inconsistent naming breaks documented import paths.

**Current Code:** File is named `common.constant.ts`; imports use mixed relative paths (`../../shared/constants/common.constant` vs `~/shared/constants/common.constant`).

**Recommended Fix:** Rename to `common.constants.ts` and standardize all imports to `~/shared/constants/common.constants`.

---

## Inline Style Summary (Additional Files)

The following files also contain inline `style={{}}` violations against `docs/skills/css-style-sheet.instructions.mdc`. Each requires migration to co-located SCSS modules:

| File | Inline style count |
|------|--------------------|
| `src/pages/report/views/JsonSnippetComparison.tsx` | 50 |
| `src/pages/admin/sections/WorkspaceMgmtSubView.tsx` | 43 |
| `src/pages/validation/steps/FixedWidthLayoutPanel.tsx` | 40 |
| `src/pages/validation/steps/JsonParentMappingStep.tsx` | 27 |
| `src/pages/report/step/Saved.tsx` | 21 |
| `src/pages/report/step/Completed.tsx` | 21 |
| `src/pages/dashboard/components/WorkspacesPanel.tsx` | 21 |
| `src/pages/validation/steps/MappingOverviewStep.tsx` | 21 |
| `src/pages/validation/ValidationWizardView.tsx` | 15 |
| `src/pages/admin/AdminView.tsx` | 14 |
| `src/pages/validation/steps/ArchiveValidationStep.tsx` | 14 |
| `src/pages/dashboard/components/TaskRow.tsx` | 13 |
| `src/pages/report/Report.tsx` | 12 |
| `src/pages/dashboard/components/EntityCustomizer.tsx` | 12 |
| `src/pages/report/step/Active.tsx` | 19 |
| `src/components/ui/FileRow.tsx` | 8 |
| `src/components/ui/MetricCard.tsx` | 7 |
| `src/layouts/BaseLayout.tsx` | 7 |
| `src/pages/dashboard/components/ActiveTasksPanel.tsx` | 6 |
| `src/pages/dashboard/components/PerformanceChartPanel.tsx` | 8 |
| `src/routes/ProtectedRoute.tsx` | 1 |
| `src/shared/FormatDetectionChainLabel.tsx` | 1 |

**Recommended Fix (all):** Replace inline styles with SCSS module classes referencing design tokens from `src/styles/tokens.css`.

---

## Compliance Summary

| Category | Violations | Severity |
|----------|-----------|----------|
| Architecture & Routing | 5 | High |
| Redux & Saga | 8 | High |
| API Layer (direct calls) | 8 | High |
| Styling (inline / SCSS) | 9 + 22 files | High |
| Font & Color | 3 | Medium |
| Testing | 1 (all features) | High |
| TypeScript & Conventions | 4 | Medium |

**Positive findings:**
- No `createAsyncThunk` usage detected (compliant with saga-only rule).
- No class components detected.
- No `moment` library usage.
- Core features (`dashboard`, `validation`, `admin`, `test`) use `createSlice` correctly (except `profile`).
- Several sagas (`Dashboard`, `Setting`, `Test`) correctly use `NOTIFICATION_SERVICE_TYPES`.

---

*Generated by automated compliance audit against project documentation.*
