# Pegasus Frontend — Codebase Rule Compliance Audit

**Audit date:** 2026-06-28  
**Scope:** `src/` audited against `agent-instructions.md`, `docs/skills/`, `docs/font/`, and `docs/color/`  
**Summary:** 24 distinct violations identified across routing, API layer, Redux/Saga notifications, runtime composition, import conventions, and styling/colors.

---

## Architectural & Routing Violations

### 1. `src/router/router.tsx`

**Rule Broken:** `docs/skills/ui-architecture.instructions.mdc` and `docs/skills/react-code-style.instructions.mdc` — keep route paths in `PATHS` constants instead of hardcoding path strings.

**Current Code:**
```tsx
{
  index: true,
  element: <Navigate to="workspace-management" replace />,
},
{
  path: 'workspace-management',
  // ...
},
{
  path: 'configure-store',
  // ...
},
{
  path: 'settings',
  // ...
},
```

**Recommended Fix:** Add admin child segment constants to `router.constants.ts` (e.g., `ADMIN_WORKSPACE_SEGMENT`, or reuse full `PATHS.ADMIN_WORKSPACE` with a path helper) and reference them in the route tree and navigations.

---

### 2. `src/pages/validation/validationRoutes.ts`

**Rule Broken:** Route paths must live in `PATHS` (`router.constants.ts`), not duplicated as inline strings.

**Current Code:**
```ts
export const VALIDATIONS_BASE = '/validations';

export const validationOverviewPath = (runId: string) =>
  `${VALIDATIONS_BASE}/overview/${runId}`;
```

**Recommended Fix:**
```ts
import { PATHS } from '~/router/router.constants';

export const VALIDATIONS_BASE = PATHS.VALIDATIONS;
export const validationOverviewPath = (runId: string) =>
  `${PATHS.VALIDATIONS}/overview/${runId}`;
```

---

### 3. `src/pages/admin/AdminView.tsx`

**Rule Broken:** `docs/skills/ui-architecture.instructions.mdc` — do not bypass `PATHS` and hardcode route strings.

**Current Code:**
```tsx
onClick={() => navigate('/admin/workspace-management')}
onClick={() => navigate('/admin/configure-store')}
onClick={() => navigate('/admin/settings')}
```

**Recommended Fix:**
```tsx
import { PATHS } from '~/router/router.constants';

onClick={() => navigate(PATHS.ADMIN_WORKSPACE)}
onClick={() => navigate(PATHS.ADMIN_CONFIGURE_STORE)}
onClick={() => navigate(PATHS.ADMIN_SETTINGS)}
```

---

### 4. `src/pages/report/views/ExecutionHistory.tsx`

**Rule Broken:** Hardcoded route strings instead of `PATHS` constants.

**Current Code:**
```tsx
onClick={() => navigate('/reports')}
onClick={() => mappingId && navigate(`/reports/${mappingId}/history/${run.run_id}/snippet`)}
```

**Recommended Fix:** Import `PATHS` and add path-builder helpers (e.g., `reportHistoryPath(mappingId)`, `reportSnippetPath(mappingId, runId)`) in `router.constants.ts` or `router.utils.ts`.

---

### 5. `src/pages/report/views/SnippetComparison.tsx` and `src/pages/report/views/JsonSnippetComparison.tsx`

**Rule Broken:** Hardcoded `/reports` breadcrumb navigation.

**Current Code:**
```tsx
onClick={() => navigate('/reports')}
```

**Recommended Fix:**
```tsx
import { PATHS } from '~/router/router.constants';
onClick={() => navigate(PATHS.REPORTS)}
```

---

### 6. `src/pages/report/step/Active.tsx`, `Completed.tsx`, `Saved.tsx`

**Rule Broken:** Hardcoded dynamic report history paths.

**Current Code:**
```tsx
onClick={() => navigate(`/reports/${report.id}/history`)}
```

**Recommended Fix:**
```tsx
import { reportHistoryPath } from '~/router/router.utils';
onClick={() => navigate(reportHistoryPath(report.id))}
```

---

### 7. `src/pages/validation/ValidationHistoryNavigation.tsx`

**Rule Broken:** Hardcoded route string in navigation side-effect.

**Current Code:**
```tsx
navigate(`/reports/${mappingId}/history`);
```

**Recommended Fix:** Use a shared `reportHistoryPath(mappingId)` helper backed by `PATHS.REPORT_HISTORY`.

---

### 8. `src/pages/validation/steps/FileSelectionStep.tsx`

**Rule Broken:** Hardcoded admin route in JSX link.

**Current Code:**
```tsx
<Link to="/admin" className={styles.adminLink}>Sign in as admin</Link>
```

**Recommended Fix:**
```tsx
<Link to={PATHS.ADMIN} className={styles.adminLink}>Sign in as admin</Link>
```

---

### 9. `src/main.tsx`

**Rule Broken:** `docs/skills/ui-architecture.instructions.mdc` — global wrapper order requires `ModalProvider` before `App`.

**Current Code:**
```tsx
<Provider store={store}>
  {/* ModalProvider will go here once implemented */}
  <App />
</Provider>
```

**Recommended Fix:** Implement and wrap the app with `ModalProvider` from `~/shared/contexts/` (or add the shared context module per architecture docs) in the documented bootstrap order.

---

## API Layer Violations (Direct Calls in Components / Bypassing Interceptors)

### 10. `src/pages/validation/steps/JsonParentMappingStep.tsx`

**Rule Broken:** `docs/skills/react-code-style.instructions.mdc` and `docs/skills/redux-and-saga.instructions.mdc` — no direct API calls in presentation components.

**Current Code:**
```tsx
Api.previewJsonParentMapping({
  source_cloud: validationForm.sourceCloud,
  target_cloud: validationForm.targetCloud,
  // ...
})
  .then((res) => { /* setState */ })
```

**Recommended Fix:** Add `previewJsonParentMapping` to `Validation.service.ts`, wire `previewJsonParentMappingRequest/Success/Error` in the reducer and saga, and dispatch from the component.

---

### 11. `src/pages/validation/ValidationWizardView.tsx` (via `validationRerun.ts`)

**Rule Broken:** Component triggers network I/O outside the saga layer.

**Current Code:**
```tsx
loadValidationRunForm(runId)
  .then((formPatch) => {
    dispatch(validationActions.setValidationForm(formPatch));
  })
```
`loadValidationRunForm` in `validationRerun.ts` calls `Api.getValidationHistoryRun` and `Api.listCloudConnections` directly.

**Recommended Fix:** Move run-loading into `Validation.service.ts` + `Validation.saga.ts` (`loadValidationRunRequest/Success/Error`) and dispatch `validationActions.loadValidationRunRequest(runId)` from the wizard.

---

### 12. `src/pages/validation/ValidationHistoryNavigation.tsx`

**Rule Broken:** Presentation component calls service-layer API directly instead of dispatching a saga action.

**Current Code:**
```tsx
const mappingId = await ReportService.getMappingIdForPaths(
  pending.sourcePath,
  pending.targetPath,
);
```

**Recommended Fix:** Dispatch a saga action (e.g., `validationActions.resolveHistoryNavigationRequest`) that calls the service and navigates on success.

---

### 13. `src/pages/auth/Login.tsx`

**Rule Broken:** Direct `adminLogin` API call in a presentation component; auth flows should use service + saga (or a dedicated auth service module invoked from saga).

**Current Code:**
```tsx
const user = await adminLogin(email.trim(), password);
dispatch(authActions.setSession({ email: user.email }));
```

**Recommended Fix:** Add `Auth.service.ts` + `Auth.saga.ts`, dispatch `authActions.loginRequest`, and handle success/error in the saga with `NOTIFICATION_SERVICE_TYPES`.

---

### 14. `src/pages/admin/AdminView.tsx` and `src/pages/auth/AuthSessionManager.tsx`

**Rule Broken:** Direct calls to `fetchAdminMe`, `adminLogout`, `fetchAdminSessionStatus`, and `extendAdminSession` from UI components instead of saga-orchestrated flows.

**Current Code (representative):**
```tsx
const user = await fetchAdminMe();
await adminLogout();
const status = await fetchAdminSessionStatus();
await extendAdminSession();
```

**Recommended Fix:** Centralize session bootstrap, extension, and logout in `Auth.service.ts` + `Auth.saga.ts` (register in `redux/saga.ts`) and dispatch slice actions from components.

---

### 15. `src/pages/test/Test.service.ts` and `src/pages/admin/sections/setting/Setting.service.ts`

**Rule Broken:** `agent-instructions.md` §3 and `docs/skills/ui-architecture.instructions.mdc` — axios must use the app-wide interceptor client (`httpClient` from `src/axios-interceptor.ts` setup), not a separate raw `axios` instance.

**Current Code:**
```ts
import axios from 'axios';
return axios.get<TestEntity[]>(`${PELICAN_BASE_PATH}${SERVICE_ENDPOINT.TESTS_ACTIVE}`);
```

**Recommended Fix:**
```ts
import { httpClient } from '~/shared/api/httpClient';
return httpClient.get<TestEntity[]>(SERVICE_ENDPOINT.TESTS_ACTIVE);
```

---

## Redux & Saga Violations

### 16. `src/pages/validation/Validation.saga.ts`

**Rule Broken:** `docs/skills/redux-and-saga.instructions.mdc` and `docs/skills/react-code-style.instructions.mdc` — use `NOTIFICATION_SERVICE_TYPES` for notification titles, not hardcoded strings.

**Current Code:**
```ts
notification.success({
  message: 'Validation complete',
  description: result.summary.is_match ? 'All checks passed.' : 'View results in execution history.',
});
// ...
notification.error({
  message: 'Could not start validation',
  description: getApiErrorMessage(error, 'Failed to run from saved configuration'),
});
// ...
message: action.payload.intent === 'proceed'
  ? 'Could not start file overview'
  : NOTIFICATION_SERVICE_TYPES.ERROR,
```

**Recommended Fix:**
```ts
notification.success({
  message: NOTIFICATION_SERVICE_TYPES.SUCCESS,
  description: 'Validation complete. ' + (result.summary.is_match ? 'All checks passed.' : 'View results in execution history.'),
});
notification.error({
  message: NOTIFICATION_SERVICE_TYPES.ERROR,
  description: getApiErrorMessage(error, 'Failed to run validation'),
});
```

---

## Import Convention Violations

### 17. Multiple feature modules under `src/pages/**`

**Rule Broken:** `docs/skills/react-code-style.instructions.mdc` — internal imports should use the `~/` alias.

**Current Code (representative):**
```tsx
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { EntityInsight } from '../../../shared/api/Api';
```

**Affected production files include:** `Dashboard.tsx`, `AdminView.tsx`, `ValidationWizardView.tsx`, `FileSelectionStep.tsx`, `AuthSessionManager.tsx`, `ExecutionHistory.tsx`, and most validation/report step components.

**Recommended Fix:**
```tsx
import { useAppDispatch, useAppSelector } from '~/redux/store';
import { EntityInsight } from '~/shared/api/Api';
```

---

## Styling & Color Violations

### 18. `src/pages/profile/Profile.module.scss`

**Rule Broken:** `docs/skills/css-style-sheet.instructions.mdc` — no new colors in module SCSS; use tokens from `src/assets/styles/variables.scss`. `agent-instructions.md` §6 — do not introduce colors outside `docs/color/` palette.

**Current Code:**
```scss
$primary: #053447;
$on-surface: #191c1e;
$outline: #72787d;
$surface-container-lowest: #ffffff;
$primary-fixed: #c3e8ff;
```

**Recommended Fix:** Remove local palette redefinitions and reference shared tokens:
```scss
@use '~/assets/styles/variables' as tokens;
.card {
  background-color: tokens.$surface-container-lowest;
  color: tokens.$on-surface;
}
```

---

### 19. `src/pages/admin/sections/WorkspaceMgmtSubView.module.scss`

**Rule Broken:** Hardcoded hex colors outside the shared palette variables.

**Current Code:**
```scss
background-color: #f0fdf4;
color: #15803d;
border: 1px solid #bbf7d0;
background-color: #fffbeb;
color: #b45309;
```

**Recommended Fix:** Replace with semantic tokens from `variables.scss` (e.g., `tokens.$status-pass`, `tokens.$status-pass-bg`, `tokens.$status-running`) or add approved equivalents to `variables.scss` if missing.

---

### 20. `src/pages/admin/Admin.module.scss` and `src/pages/admin/sections/ConfigureStoreSubView.module.scss`

**Rule Broken:** Hardcoded hex/rgba brand and status colors (`#4285f4`, `#727786`, `#52c41a`, `#faad14`, `#d9d9d9`, etc.) instead of shared SCSS variables.

**Current Code (representative):**
```scss
color: #4285f4;
background-color: rgba(66, 133, 244, 0.12);
border: 1px solid #d9d9d9;
```

**Recommended Fix:** Map each usage to `variables.scss` tokens (`$primary`, `$outline-variant`, `$status-pass`, `$border-1`, etc.) via `@use '~/assets/styles/variables' as tokens;`.

---

### 21. `src/pages/validation/steps/ConfigureMappingStep.module.scss`

**Rule Broken:** Extensive hardcoded Tailwind-like palette (`#4f46e5`, `#eef2ff`, `#eff6ff`, `#1e40af`, etc.) not sourced from `variables.scss` or CSS custom properties.

**Current Code (representative):**
```scss
background-color: #eff6ff;
border: 1px solid #bfdbfe;
color: #1e40af;
border-color: #6366f1;
background: #4f46e5;
```

**Recommended Fix:** Replace with `tokens.$primary`, `tokens.$primary-fixed`, `tokens.$inverse-primary`, and related approved palette entries; remove ad-hoc indigo/blue literals.

---

### 22. `src/pages/validation/steps/MappingOverviewStep.module.scss`, `FixedWidthLayoutPanel.module.scss`, `JsonParentMappingStep.module.scss`, `FileSelectionStep.module.scss`, `ArchiveValidationStep.module.scss`, `OverviewFilePreview.module.scss`

**Rule Broken:** Repeated hardcoded grays, borders, and status colors (`#727786`, `#d9d9d9`, `#dc2626`, `#fef2f2`, `#e2e8f0`, etc.).

**Current Code (representative):**
```scss
color: #727786;
border: 1px solid #d9d9d9;
background-color: #fef2f2;
color: #dc2626;
```

**Recommended Fix:** Consolidate to shared variables (`$on-surface-variant`, `$outline-variant`, `$error`, `$error-container`, `$border-subtle`) from `variables.scss`.

---

### 23. `src/pages/report/views/SnippetComparison.module.scss` and `JsonSnippetComparison.module.scss`

**Rule Broken:** Hardcoded diff/highlight palette (`#1e293b`, `#991b1b`, `#fee2e2`, `#fff7ed`, `#c2410c`, `#a0aabf`) outside approved tokens.

**Current Code (representative):**
```scss
background-color: #1e293b;
color: #991b1b;
background-color: #fee2e2;
color: #c2410c;
```

**Recommended Fix:** Use semantic status tokens (`$status-fail`, `$status-fail-bg`, `$status-running`, `$on-surface`, `$text-muted`) defined in `variables.scss`.

---

### 24. `src/pages/auth/Auth.module.scss`

**Rule Broken:** Introduces undeclared color outside shared palette.

**Current Code:**
```scss
color: #1b73e8;
```

**Recommended Fix:**
```scss
color: tokens.$color-midnight-green-accent; // or tokens.$secondary
```

---

## Items Verified Compliant (Previously Reported, Now Fixed)

The following major areas from the prior audit are now compliant:

- `createHashRouter` with lazy-loaded routes in `src/router/router.tsx`
- `AuthGuard` replaces legacy `ProtectedRoute`
- `src/axios-interceptor.ts` exists and is imported from `main.tsx`
- `Header.tsx` uses `PATHS` constants
- Profile, Report, and Auth reducers use `createSlice` with `{ data, isFetching, error }` shape
- Sagas use `takeLatest`, typed slice actions, and `AxiosError` branching (Report, Profile, Dashboard, Setting, Test)
- No `BrowserRouter`, `createAsyncThunk`, `moment`, inline `style={{}}`, plain `.css` files, or class components in `src/`
- Plus Jakarta Sans configured in `variables.scss` and `main.tsx` `ConfigProvider`
- Co-located `.module.scss` files present for route-level and step components
- Direct `Api.*` calls removed from `FileSelectionStep`, `ConfigureMappingStep`, and `MappingOverviewStep` (now saga-driven)
