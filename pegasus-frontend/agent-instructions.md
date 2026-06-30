# Pegasus Frontend - Agent Instructions

## 1. Agent Initialization & First Steps
**CRITICAL STRICT DIRECTIVE:** You must not pull context from, read, or scan the `.gsd/` or `.bg-shell/` directories under any circumstances. Rely exclusively on user prompts and this instruction file (`agent-instructions.md`) for project context.

**CRITICAL:** Before writing any code or making architectural decisions, you must review and apply the strict rules and regulations laid out in the `docs/` folder. 

Currently, the `docs/` directory is strictly organized into three subfolders containing our core standards:
1. **`docs/skills/`**: Contains all foundational coding guidelines (e.g., Frontend Conventions, React Code Style, CSS/SCSS conventions, Redux & Saga implementation rules, UI Architecture, and Unit Testing guidelines). 
2. **`docs/font/`**: Contains font asset information (Plus Jakarta Sans).
3. **`docs/color/`**: Contains our strict color palette guidelines.

*Note on other documentation:* The files in the `docs/` folder are the only explicitly segregated architectural rules. Any other documentation files (such as algorithm descriptions) are currently scattered and dumped directly in the root of the `Pegasus-Frontend` folder.

---

## 2. Project Overview & Context
- **Project Name:** Pegasus
- **Focus Area:** `Pegasus-Frontend`
- **Backend/Deployment:** The root Pegasus folder contains `Pegasus-Backend`, customization `Scripts`, `test-data`, and Docker configurations (`docker-compose.yml`, `docker-compose.overide.example.yml`) to orchestrate the full stack.

---

## 3. Tech Stack
- **Core:** React 18, TypeScript, Vite
- **Routing:** React Router v6 (`createHashRouter` with lazy loading)
- **State Management:** Redux Toolkit + Redux Saga
- **UI & Styling:** Ant Design v5, SCSS Modules, Bootstrap utility classes
- **API:** Axios (configured with app-wide interceptors in `src/axios-interceptor.ts`)
- **Testing:** Vitest + Testing Library

---

## 4. Directory Structure
The frontend follows a feature-first module structure. 

```text
Pegasus-Frontend/
├── docs/                      # Core organized guidelines (skills/, font/, color/)
├── *.md / *.txt               # Other scattered documentation dumped in the root
├── node_modules/              
├── public/                    # Static public assets
├── src/                       # Main application source code
│   ├── assets/                # Default react, vite, and hero icons
│   ├── components/UI/         # Shared global UI (Filerow.tsx, Header.tsx, MetricCard.tsx)
│   ├── layouts/               # BaseLayout.tsx for structural app layout
│   ├── redux/                 # Root reducer.ts, saga.ts, and store.ts
│   ├── routes/                # AppRoutes.tsx, ProtectedRoute.tsx (Auth gating)
│   ├── shared/                
│   │   ├── api/               # adminAuth.ts, Api.ts, apiError.ts, httpClient.ts
│   │   ├── constants/         # common.constants.ts, service-endpoints.constants.ts
│   │   └── styles/            # token.cssc (global layout styles)
│   └── pages/                 # Feature modules (See Section 5)
├── Dockerfile                 # Frontend containerization
├── eslint.config.js           
├── package.json               
├── tsconfig.json              
└── vite.config.ts
```

---

## 5. Feature Modules (`src/pages/`)
Each feature module encapsulates its own components, reducers, sagas, services, and interfaces.

- **`admin/`**: Admin management (`AdminView.tsx`). Includes `sections/` (`ConfigureStoreSubView`, `ConnectStorageModal`, `WorkspaceMgmtSubView`) and `sections/setting/` (`Setting` with its own reducer, saga, and service).
- **`auth/`**: Authentication flow (`Login`, `AuthSessionManager`, `Auth.reducer`).
- **`dashboard/`**: Main dashboard view (`Dashboard.tsx`). Includes `components/` (`ActiveTasksPanel`, `EntityCustomizer`, `MetricsPanel`, `PerformanceChartPanel`, `TaskRow`, `WorkspacesPanel`).
- **`profile/`**: User profile view (`Profile.tsx` with reducer, saga, and service).
- **`report/`**: **[ACTIVE]** Reporting UI (`Report.tsx`). Contains `step/` (`Active`, `Completed`, `Saved`) and `views/` (`ExecutionHistory`, `JsonSnippetComparison`, `SnippetComparison`, `SnippetViewRouter`).
- **`test/`**: Test harness view (`TestView.tsx`). Includes `components/` (`ActiveView`, `Completed`, `SavedView`) with full Redux/Saga stack.
- **`validation/`**: Validation workflow (`ValidationWizardView.tsx`). Includes `steps/` (`ArchiveValidationStep`, `ConfigureMappingStep`, `FileSelectionStep`, `FixedWidthLayoutPanel`, `JsonParentMappingStep`, `MappingOverviewStep`, `OverviewFilePreview`, `OverviewJsonPreview`) plus session/routing utilities (`ValidationHistoryNavigation`, `ValidationTabSessionGuard`, `validationRoutes`, format helpers).

**Removed:** The legacy `history/` module has been deleted; reporting is handled exclusively by `report/`.

---

## 6. `src/shared/` — Do Not Modify (Temporary)
**CRITICAL:** Do **not** make any changes under `src/shared/` (including `api/`, `constants/`, and `styles/`) until the user has provided the API endpoints and parameters to use. All snippet/report work must use existing shared exports as-is; place new logic in feature modules (e.g. `src/pages/report/`) only.

---

## 7. High-Level Coding Conventions
*(Refer to `docs/skills/` for the exhaustive rules)*

* **Components:** Functional components only. Default exports for route-level features. Typed props via co-located `*.interface.ts` files.
* **State Management:** Redux Toolkit (`createSlice`) + Redux Saga (`takeLatest`). Standard state shape: `{ data, isFetching, error }`. No `createAsyncThunk`.
* **Styling:** Co-located CSS Modules (`*.module.scss`). Use Ant Design layout components (`Row`, `Col`, `Flex`) and Bootstrap utilities for spacing. Do not introduce new colors or fonts outside of the guidelines in `docs/color/` and `docs/font/`.
* **Testing:** Co-locate tests in `tests/` folders. Use `renderWithProviders` and target stable `data-testid` attributes.