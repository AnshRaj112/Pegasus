## Frontend — pelican-ui-v2

**Stack:** React 18.3, TypeScript 5.2, Vite 5.4, Redux Toolkit 2.3, Redux Saga 1.3, React Router DOM 6.27 (HashRouter), Ant Design 5.21, Axios, SCSS Modules, Vitest, Testing Library.

### Architecture

```
App.tsx  →  Router (HashRouter, lazy-loaded routes)
               ↓
         Layout (Bootstrap / Pages / Index)
               ↓
         Page Component  ←→  Redux Slice + Saga  ←→  Service (axios)
               ↓
         Shared Components (Ant Design + custom)
```

### Conventions

- **Components:** Functional, with hooks. Props defined via TypeScript interfaces. Styles in `*.module.scss`.
- **State management:** Redux Toolkit `createSlice`. Async side-effects via Redux Saga (`takeLatest`). Standard state shape: `{ data: T | null, isFetching: boolean, error: string | null }`. Typed hooks: `useAppDispatch`, `useAppSelector`.
- **Action pattern:** Request / Success / Error triad per async operation.
- **API layer:** Service files (`*.service.ts`) wrap axios calls. Endpoints centralised in `shared/constants/service-endpoints.constants.ts`. Axios interceptors handle request IDs (UUID), CSRF tokens, request cancellation (GET dedup), and 401/403 redirects.
- **Routing:** `createHashRouter` in `router/router.tsx`. Route constants in `router/router.constants.tsx`. Protected by `AuthGuard` (permission + role + feature checks).
- **Styling:** SCSS Modules per component. Global variables/mixins in `assets/styles/`. Ant Design theme via `themeConfig.ts`.
- **Testing:** Vitest + Testing Library + Happy DOM. `renderWithProviders` utility wraps Redux store. `vi.mock()` for dependencies.

### Page Module Structure

Each feature page typically contains:

```
pages/feature-name/
├── FeatureName.tsx              # Main component
├── FeatureName.reducer.ts       # Redux slice
├── FeatureName.saga.ts          # Saga
├── FeatureName.service.ts       # API calls
├── FeatureName.interface.ts     # TypeScript interfaces
├── FeatureName.module.scss      # Styles
├── components/                  # Sub-components
└── tests/                       # Test files
```

### Key Shared Resources

| Path | Purpose |
|------|---------|
| `shared/constants/service-endpoints.constants.ts` | All API endpoint paths |
| `shared/constants/common.constants.ts` | App-wide constants |
| `shared/common-utils.tsx` | Date formatting, file downloads, clipboard |
| `shared/common-table-utils.tsx` | Table/grid helpers |
| `shared/hooks/` | `useIdleTimeout`, `useWebSocket` |
| `shared/contexts/` | `HeaderContext`, `ModalContext` |
| `components/access-control/` | Permission-based component rendering |
| `components/auth-guard/` | Route-level auth guard |

### Build & Dev

- `npm run dev` — Vite dev server with backend proxy.
- `npm run build` — Production build with code splitting (vendor chunks for React, lodash, apexcharts, ace-editor).
- Path aliases: `~/` and `src/` both resolve to `src/`.

---
