# Testing Guide — React + Vite + Vitest

---

## Table of Contents

1. [What is Testing and Why Do We Do It?](#1-what-is-testing-and-why-do-we-do-it)
2. [The Three Levels of Testing](#2-the-three-levels-of-testing)
3. [Why Unit Testing Fits React Applications](#3-why-unit-testing-fits-react-applications)
4. [What We Test in a Feature Slice](#4-what-we-test-in-a-feature-slice)
5. [The Tool Stack](#5-the-tool-stack)
6. [Installation](#6-installation)
7. [How the Setup Boots — File by File](#7-how-the-setup-boots--file-by-file)
8. [What a Test Looks Like — Four Examples](#8-what-a-test-looks-like--four-examples)
9. [Writing Tests: Patterns and Rules](#9-writing-tests-patterns-and-rules)
10. [What to Test. What to Skip.](#10-what-to-test-what-to-skip)
11. [Running Tests](#11-running-tests)
12. [Quick Reference](#12-quick-reference)

---

## 1. What is Testing and Why Do We Do It?

Software testing is the practice of verifying that code does what it is supposed to do — automatically, repeatably, and without a human clicking through the app every time a change is made.

Without tests, the only way to know if something works is to run the whole application and manually check. That does not scale. A single change in a shared utility can silently break five features, and you only find out when a user reports a bug in production.

With tests, every change is automatically checked against a defined set of expected behaviours. The moment something breaks, the test suite tells you exactly which expectation was violated and where.

---

## 2. The Three Levels of Testing

All software tests fall into three broad categories. They trade off speed, realism, and maintenance cost differently.

```
                  ┌──────────────────────────────────────────┐
  Fewest / Slowest│  End-to-End (E2E)                        │
                  │  Real browser + real server               │
                  │  "A user logs in and sees their dashboard"│
                  ├──────────────────────────────────────────┤
                  │  Integration                              │
                  │  Multiple units wired together            │
                  │  "Component re-renders after store update"│
  Most / Fastest  ├──────────────────────────────────────────┤
                  │  Unit                                     │
                  │  One function or component in isolation   │
                  │  "Reducer sets loading: true on request"  │
                  └──────────────────────────────────────────┘
```

| Level | Tests what | Speed | Setup cost | Failure signal |
|---|---|---|---|---|
| **Unit** | One isolated piece | Milliseconds | Minimal | Exact function that broke |
| **Integration** | Multiple pieces together | Seconds | Moderate | Somewhere in the chain |
| **E2E** | The whole app in a browser | Minutes | High | Browser-level symptom |

**Integration testing** checks that units interact correctly — for example, whether a component re-renders after the store updates. These tests are more realistic but slower and harder to diagnose when they fail.

**Unit testing** is the first line of defence: fast, isolated, and zero backend dependency. Integration and E2E tests are added for critical flows that unit tests cannot cover.

---

## 3. Why Unit Testing Fits React Applications

A React application built with Redux and async side-effect handling (thunks, sagas, or similar) naturally decomposes into isolated, testable units:

- A **reducer** is a pure function: `(state, action) → newState`. No side effects. Test it by passing in state and an action, then assert the output.
- A **saga or thunk** orchestrates async work by yielding or awaiting effects. Test it by stepping through those effects and asserting each one — no real network call needed.
- A **component** takes props and renders JSX. Test it by mounting it in a fake DOM and asserting what appears on screen.
- A **helper** is a pure data-transformation function. Test it by calling it with input and asserting the output.

Every one of these can be tested without a running server, a real browser, or any external dependency. That is what makes unit testing the right fit.

---

## 4. What We Test in a Feature Slice

A well-structured feature has its code and tests colocated:

```
src/pages/user-profile/
├── UserProfile.tsx              ← React component
├── UserProfile.reducer.ts       ← Redux reducer
├── UserProfile.saga.ts          ← Side effects (API calls)
├── UserProfileHelpers.ts        ← Pure data-transformation functions
├── UserProfile.mockData.ts      ← Shared mock data for all test files
└── tests/
    ├── UserProfile.test.tsx          ← component tests
    ├── UserProfile.reducer.test.ts   ← reducer tests
    ├── UserProfile.saga.test.ts      ← saga / async tests
    └── UserProfile.helper.test.ts    ← helper function tests
```

Each layer is tested in its own file. All test files in a feature share a single `mockData` file so test data is defined once and maintained in one place.

| Layer | File pattern | What you verify |
|---|---|---|
| Component | `*.test.tsx` | Correct elements on screen, labels, buttons, placeholders |
| Reducer | `*.reducer.test.ts` | State shape after Progress / Success / Failure / Reset actions |
| Saga | `*.saga.test.ts` | Effects yielded in the right order: dispatch → call → dispatch |
| Helper | `*.helper.test.ts` | Output shape, length, and correctness for a given input |

---

## 5. The Tool Stack

Four libraries, each with a single job:

```
┌──────────────────────────────────────────────────────────────────┐
│  Your test file  (.test.tsx / .test.ts)                          │
│  describe  it  expect  vi.fn  beforeEach  afterEach              │
│                         ↑ Vitest provides all of these           │
├──────────────────────────────────────────────────────────────────┤
│  @testing-library/react                                          │
│  render()   screen   fireEvent   waitFor   within                │
│  Mounts a component into the fake DOM and lets you query it      │
├──────────────────────────────────────────────────────────────────┤
│  @testing-library/jest-dom                                       │
│  toBeInTheDocument()  toBeDisabled()  toHaveValue()              │
│  Adds readable DOM-specific matchers to expect()                 │
├──────────────────────────────────────────────────────────────────┤
│  happy-dom                                                       │
│  Simulates window / document / DOM inside Node.js                │
│  No real browser is ever opened                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Vitest — the test runner

Finds your test files, runs them in a sandboxed environment, and reports pass/fail. It is built on top of Vite, so it reuses the same config, path aliases, and TypeScript setup the app already has. Its API is identical to Jest — `describe`, `it`, `expect`, `vi.fn()`, `beforeEach` — so nothing is new if you have used Jest before.

### @testing-library/react (RTL)

Gives you `render()` to mount a component into a fake DOM, `screen` to find elements by what the user sees (text, label, role), `fireEvent` to simulate interactions, and `waitFor` to handle async updates.

The core philosophy: **test what the user sees, not how the code works internally.** Query by visible text and ARIA roles, not by class names or internal component state. If you refactor a component's internals but the output is the same, the test should still pass.

### happy-dom

Node.js has no `window`, no `document`, and no DOM. `happy-dom` is a lightweight simulation of the browser environment that runs inside Node.js. React needs this to render component trees during tests. It is faster than the alternative (`jsdom`) and sufficient for component-level testing.

### @testing-library/jest-dom

Extends `expect()` with matchers that read naturally for DOM assertions:

```ts
// Without jest-dom — works but reads awkwardly:
expect(document.body.contains(element)).toBe(true)

// With jest-dom — clear and precise:
expect(element).toBeInTheDocument()
expect(button).toBeDisabled()
expect(input).toHaveValue('user@example.com')
expect(card).toHaveTextContent('Settings')
```

---

## 6. Installation

### Prerequisites

- **Node.js** ≥ 18
- **npm** ≥ 9 (ships with Node 18)

```bash
node -v   # should print v18.x.x or higher
npm -v    # should print 9.x.x or higher
```

### Step 1 — Install the packages

```bash
npm install --save-dev vitest @vitejs/plugin-react-swc happy-dom
npm install --save-dev @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

What each package does:

| Package | Role |
|---|---|
| `vitest` | Test runner — finds `.test.ts/tsx` files, runs them, reports pass/fail |
| `@vitejs/plugin-react-swc` | Transforms JSX/TSX in test files using SWC (same plugin Vite uses) |
| `happy-dom` | Simulates `window`, `document`, and DOM inside Node.js |
| `@testing-library/react` | `render()`, `screen`, `fireEvent`, `waitFor` — mounts and queries components |
| `@testing-library/jest-dom` | Readable DOM matchers: `toBeInTheDocument()`, `toHaveValue()`, etc. |
| `@testing-library/user-event` | Simulates realistic user interactions (typing, clicking, tabbing) |

### Step 2 — Create `vitest.config.ts`

Place this file at the project root, next to `vite.config.ts`:

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: './src/setupTests.ts',
  },
})
```

| Option | Why |
|---|---|
| `plugins: [react()]` | Without this, `.tsx` files fail to parse: `Unexpected token '<'` |
| `globals: true` | Makes `describe`, `it`, `expect`, `vi` available without importing in every file |
| `environment: 'happy-dom'` | Without this, `document is not defined` — React cannot render |
| `setupFiles` | Runs a setup file before every test file to register matchers and browser stubs |

**With path aliases** (if your project uses `~/` or similar):

```ts
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '~/': `${path.resolve(__dirname, 'src')}/`,
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: './src/setupTests.ts',
  },
})
```

### Step 3 — Create `src/setupTests.ts`

```ts
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom'
import '@testing-library/jest-dom/vitest'

afterEach(() => {
  cleanup()
})
```

`cleanup()` unmounts every component after each test so DOM elements do not leak between tests. Both jest-dom imports are required — the second one patches the matchers into Vitest's `expect`.

**Additional stubs for common browser APIs** that `happy-dom` does not implement — add these if your UI library or charting library calls them:

```ts
import { vi } from 'vitest'

// Required by many UI libraries (e.g. Ant Design) for responsive behaviour
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Required by SVG-based charting libraries
window.SVGPathElement = vi.fn()

// Required when components generate file download links
if (typeof window.URL.createObjectURL === 'undefined') {
  Object.defineProperty(window.URL, 'createObjectURL', { value: () => {} })
}
```

### Step 4 — Add test scripts to `package.json`

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "test:ui": "vitest --ui"
  }
}
```

`vitest run` exits after one pass (CI-friendly). Plain `vitest` runs in watch mode and re-runs affected tests on every file save.

### Step 5 — Write your first test

```tsx
// src/components/Button.test.tsx
import { render, screen } from '@testing-library/react'
import Button from './Button'

it('renders the button label', () => {
  render(<Button label="Save" />)
  expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
})
```

```bash
npm test
```

### Optional — coverage report

```bash
npm install --save-dev @vitest/coverage-v8
npm run test:coverage
# Generates an HTML report in coverage/
```

### Troubleshooting

**`Cannot find module '~/...'`**
Path aliases are not resolving. Make sure `resolve.alias` is configured in `vitest.config.ts` and that the alias points to the correct directory.

**`toBeInTheDocument is not a function`**
jest-dom matchers are not loaded. Check that `src/setupTests.ts` imports both `@testing-library/jest-dom` and `@testing-library/jest-dom/vitest`, and that `setupFiles` in `vitest.config.ts` points to that file.

**`TypeError: window.matchMedia is not a function`**
Add the `matchMedia` stub to `src/setupTests.ts` as shown in Step 3.

**`document is not defined`**
`environment: 'happy-dom'` is missing from the `test` block in `vitest.config.ts`.

**Tests hang and never exit**
Use `vitest run` in the npm script, or add `watch: false` inside the `test` block in `vitest.config.ts`.

---

## 7. How the Setup Boots — File by File

When you run `npm test`, Vitest initialises in this exact order before running a single test:

```
npm test
    │
    ▼
① vitest.config.ts
    Defines: test environment, path aliases, global functions, setup file
    │
    ▼
② src/setupTests.ts        (runs once before every test file)
    Registers: DOM matchers, afterEach cleanup, browser API stubs
    │
    ▼
③ Your test file imports
    e.g. import { render, screen } from '@testing-library/react'
         import { render } from '~/utils/renderWithProvider'  ← if using a custom wrapper
    │
    ▼
④ Tests execute
    describe / it / expect run in the fake DOM
    │
    ▼
⑤ afterEach cleanup()
    DOM is wiped. Next test starts with a blank slate.
```

Nothing here is magic. Each file has one specific job.

---

### ① `vitest.config.ts`

Minimal config for a React + Vite project:

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react-swc'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '~/': `${path.resolve(__dirname, 'src')}/`,
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: './src/setupTests.ts',
  },
})
```

| Option | What it does | What breaks without it |
|---|---|---|
| `plugins: [react()]` | Transforms JSX/TSX in test files using SWC | `Unexpected token '<'` — `.tsx` files cannot be parsed |
| `resolve.alias` | Lets test files use the same import paths as app code | `Cannot find module '~/...'` in every test file |
| `globals: true` | Makes `describe`, `it`, `expect`, `vi` available without importing | `describe is not defined` in every test file |
| `environment: 'happy-dom'` | Provides `window`, `document`, and DOM inside Node.js | `document is not defined` — React cannot render |
| `setupFiles` | Runs `setupTests.ts` before every test file | DOM matchers missing, browser stubs not applied |

---

### ② `src/setupTests.ts`

```ts
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom'
import '@testing-library/jest-dom/vitest'

afterEach(() => {
  cleanup()
})
```

This file runs before every test file. It has three jobs:

**Job 1 — Register DOM matchers**

```ts
import '@testing-library/jest-dom'
import '@testing-library/jest-dom/vitest'
```

Loads matchers like `toBeInTheDocument()`, `toHaveValue()`, `toBeDisabled()` globally. Both imports are required — the second patches them into Vitest's `expect`.

**Job 2 — Auto-cleanup after each test**

```ts
afterEach(() => { cleanup() })
```

Unmounts every component rendered during a test and wipes the fake DOM. Without this, elements from test A remain in the DOM when test B runs, causing false positives and hard-to-diagnose failures.

**Job 3 — Stub browser APIs that `happy-dom` does not implement**

`happy-dom` is lightweight. Add stubs for any API your UI libraries call:

```ts
// Needed by UI libraries that detect media queries (e.g. responsive layout, dark mode)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Needed by SVG-based charting libraries
window.SVGPathElement = vi.fn()

// Needed when components trigger file downloads
if (typeof window.URL.createObjectURL === 'undefined') {
  Object.defineProperty(window.URL, 'createObjectURL', { value: () => {} })
}
```

---

### ③ Custom render wrapper (optional)

If your components depend on a global context — Redux store, React Router, a theme provider — wrapping every `render()` call manually is repetitive and error-prone. A custom render utility solves this:

```tsx
// src/utils/renderWithProviders.tsx
import React from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { store } from '../redux/store'

export * from '@testing-library/react'

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>
    <Provider store={store}>{children}</Provider>
  </MemoryRouter>
)

const customRender = (ui: React.ReactElement, options?: Omit<RenderOptions, 'wrapper'>) =>
  render(ui, { wrapper: Wrapper, ...options })

export { customRender as render }
```

**Why `MemoryRouter` not `BrowserRouter`?** `BrowserRouter` reads from `window.location` — the real browser URL bar, which does not exist in a test process. `MemoryRouter` keeps routing state in JavaScript memory and works in `happy-dom`.

**Why `export * from '@testing-library/react'`?** Re-exports `screen`, `fireEvent`, `waitFor`, etc. so test files need only one import:

```ts
import { render, screen, fireEvent, waitFor } from '~/utils/renderWithProviders'
```

**Preloaded state** — for tests that need specific store state up front:

```tsx
import { configureStore } from '@reduxjs/toolkit'
import reducers from '~/redux/rootReducer'

export const renderWithState = (ui: React.ReactElement, preloadedState = {}) => {
  const store = configureStore({ reducer: reducers, preloadedState })
  return render(
    <MemoryRouter><Provider store={store}>{ui}</Provider></MemoryRouter>
  )
}

// In a test:
renderWithState(<UserProfile />, {
  user: { data: null, loading: false, error: 'Not found' }
})
```

---

## 8. What a Test Looks Like — Four Examples

### Component test

```tsx
// src/pages/settings/tests/Settings.test.tsx
import { render, screen } from '~/utils/renderWithProviders'
import Settings from '../Settings'

describe('Settings', () => {

  it('renders the form', () => {
    render(<Settings />)
    expect(screen.getByLabelText(/display name/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
  })

  it('shows placeholder text on the email input', () => {
    render(<Settings />)
    expect(screen.getByPlaceholderText(/enter your email/i)).toBeInTheDocument()
  })
})
```

Key points: query by what the user sees (labels, placeholders, roles). Use `/i` regex for case-insensitive matching. Never query by CSS class name.

---

### Reducer test

```ts
// src/pages/settings/tests/Settings.reducer.test.ts
import settingsReducer, { initialState, settingsActions } from '../Settings.reducer'
import { mockUserData } from '../Settings.mockData'

const loading = (key: string) => ({ ...initialState, [key]: { ...initialState[key], loading: true } })
const success = (key: string, data: unknown) => ({ ...initialState, [key]: { data, loading: false, error: null } })
const failure = (key: string, error: string) => ({ ...initialState, [key]: { data: null, loading: false, error } })

describe('Settings reducer', () => {

  it('sets loading on fetch request', () => {
    expect(settingsReducer(initialState, settingsActions.fetchUserProgress()))
      .toEqual(loading('user'))
  })

  it('stores data on fetch success', () => {
    expect(settingsReducer(initialState, settingsActions.fetchUserSuccess(mockUserData)))
      .toEqual(success('user', mockUserData))
  })

  it('stores error on fetch failure', () => {
    expect(settingsReducer(initialState, settingsActions.fetchUserFailure('Not found')))
      .toEqual(failure('user', 'Not found'))
  })
})
```

Reducers are pure functions — pass in `(state, action)` and assert the result. The small state-builder helpers (`loading`, `success`, `failure`) prevent copy-pasting the full state object in every test.

---

### Saga test

```ts
// src/pages/settings/tests/Settings.saga.test.ts
import { call, put } from 'redux-saga/effects'
import { fetchUser } from '../Settings.saga'
import { settingsActions } from '../Settings.reducer'
import { mockUserData } from '../Settings.mockData'
import { api } from '~/service'

describe('fetchUser saga', () => {

  it('dispatches Progress as the first effect', () => {
    const iterator = fetchUser({ payload: { id: '1' } })
    expect(iterator.next().value).toEqual(put(settingsActions.fetchUserProgress()))
  })

  it('calls the API then dispatches Success', () => {
    const iterator = fetchUser({ payload: { id: '1' } })
    iterator.next()                                          // Progress

    expect(iterator.next().value).toEqual(call(api.getUser, '1'))

    expect(iterator.next(mockUserData).value).toEqual(       // inject mock response
      put(settingsActions.fetchUserSuccess(mockUserData))
    )
  })

  it('dispatches Failure when the API throws', () => {
    const iterator = fetchUser({ payload: { id: '1' } })
    iterator.next()   // Progress
    iterator.next()   // call(api)

    const error = new Error('Server error')
    expect(iterator.throw(error).value).toEqual(
      put(settingsActions.fetchUserFailure(error.message))
    )
  })
})
```

The saga is a generator — `iterator.next()` steps it one yield at a time. Pass a mock response with `iterator.next(value)`. Inject an error with `iterator.throw(error)`. No real HTTP call is ever made.

---

### Helper test

```ts
// src/pages/settings/tests/Settings.helper.test.ts
import { formatUserDisplayName, filterActiveUsers } from '../SettingsHelpers'
import { mockUsers } from '../Settings.mockData'

describe('SettingsHelpers', () => {

  it('formatUserDisplayName returns first and last name joined', () => {
    expect(formatUserDisplayName({ first: 'Jane', last: 'Doe' })).toBe('Jane Doe')
  })

  it('filterActiveUsers returns only active entries', () => {
    const result = filterActiveUsers(mockUsers)
    expect(result).toHaveLength(2)
    expect(result[0]).toMatchObject({ active: true })
  })

  it('filterActiveUsers returns empty array for empty input', () => {
    expect(filterActiveUsers([])).toEqual([])
  })
})
```

Helper tests are the simplest: call the function with mock input, assert the output. No Redux, no DOM, no async.

---

## 9. Writing Tests: Patterns and Rules

### Always import `render` from the custom wrapper, not RTL directly

```tsx
// CORRECT — component gets store + router context
import { render, screen } from '~/utils/renderWithProviders'

// WRONG — crashes when component calls useSelector or useNavigate
import { render } from '@testing-library/react'
```

### Mock third-party modules that use browser APIs unavailable in happy-dom

```ts
// At the top of any test file whose code calls notification APIs
vi.mock('some-notification-library', () => ({
  notify: { success: vi.fn(), error: vi.fn() },
}))
```

### Keep all mock data in a shared `*.mockData.ts` file

```ts
// CORRECT — one file, imported by all four test files in a feature
import { mockUser } from '../Settings.mockData'

// WRONG — duplicated in each test file; breaks when the data shape changes
const mockUser = { id: '1', name: 'Jane' }
```

### Use regex with `/i` for text queries

```ts
screen.getByText(/display name/i)              // survives capitalisation changes
screen.getByRole('button', { name: /save/i })

screen.getByText('Display Name')               // breaks if text casing changes
```

### Use `beforeEach` for repeated setup

```tsx
describe('Settings', () => {
  beforeEach(() => {
    render(<Settings />)
  })

  it('renders the display name field', () => {
    expect(screen.getByLabelText(/display name/i)).toBeInTheDocument()
  })

  it('renders the save button', () => {
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument()
  })
})
```

### Name every test as a sentence that reads as a specification

```ts
// GOOD — reads like a spec document
it('dispatches fetchUserSuccess on a 200 response', ...)
it('sets loading to true when fetch starts', ...)
it('renders the save button', ...)

// BAD — communicates nothing
it('works', ...)
it('test 1', ...)
```

### Use `getByRole` as the first-choice query

`getByRole` finds elements the same way assistive technologies do — it is the most accessible and resilient query method:

```ts
screen.getByRole('button', { name: /save/i })
screen.getByRole('textbox', { name: /display name/i })
```

Fall back to `getByLabelText`, `getByPlaceholderText`, or `getByText` only when a role-based query is not available.

---

## 10. What to Test. What to Skip.

### Test these

| What | Why |
|---|---|
| Reducer: Progress / Success / Failure / Reset transitions | Pure functions — highest value for lowest cost |
| Saga: first effect is the Progress dispatch | Verifies the loading state will appear |
| Saga: second effect calls the right API function | Catches wrong endpoint or missing payload |
| Saga: success path dispatches with the correct data shape | Catches data-mapping bugs |
| Saga: failure path dispatches with the error message | Verifies error handling exists |
| Component: required form labels are present | Catches accidental deletions of required fields |
| Component: required buttons exist | Minimum check that the UI is complete |
| Component: placeholder text on inputs | Catches UX regressions |
| Helper: return length | Catches off-by-one and filtering bugs |
| Helper: shape of the first item | Catches transform bugs |
| Helper: empty input returns empty output | Functions commonly fail on empty arrays |

### Skip these

| What | Why |
|---|---|
| CSS class names or inline styles | Change on every design update — not behaviour |
| Internal `useState` variable values | Test the DOM output, not how the component stores data internally |
| That Redux Toolkit generates actions from `createSlice` | You did not write Redux Toolkit |
| That a UI library renders the correct HTML element | You did not write the UI library |
| The exact URL string passed to the HTTP client | Test that the right function was called; URL strings are implementation details |
| Snapshot tests of full page components | Fail on every UI tweak and provide no useful diagnostic |

---

## 11. Running Tests

```bash
# Run all tests once (CI mode)
npm test
# or
npx vitest run

# Watch mode — re-runs affected tests on every file save
npx vitest

# Run a single test file
npx vitest run src/pages/settings/tests/Settings.reducer.test.ts

# Run all test files whose path matches a pattern
npx vitest run settings

# See every individual test name in the output
npx vitest run --reporter=verbose

# Generate a code coverage report
npm run test:coverage

# Open the visual test explorer in a browser
npm run test:ui
```

---

## 12. Quick Reference

### Tool summary

| Tool | Role | Key API |
|---|---|---|
| **Vitest** | Test runner | `describe` `it` `expect` `vi.fn()` `beforeEach` |
| **RTL** | Render + query components | `render` `screen` `fireEvent` `waitFor` |
| **jest-dom** | DOM assertions | `toBeInTheDocument` `toBeDisabled` `toHaveValue` |
| **happy-dom** | Fake browser in Node.js | Configured in `vitest.config.ts` — no direct API |

### Query method cheat sheet

| Method | Finds by | Use when |
|---|---|---|
| `getByRole('button', { name: /x/i })` | ARIA role + accessible name | Buttons, inputs, links — **first choice** |
| `getByLabelText(/name/i)` | `<label>` text | Form fields with labels |
| `getByPlaceholderText(/enter/i)` | `placeholder` attribute | Inputs without visible labels |
| `getByText(/save/i)` | Visible text content | Headings, paragraphs, cell content |
| `queryByText(/error/i)` | Text — returns `null` if absent | Asserting something is NOT present |
| `findByText(/loaded/i)` | Text — returns a Promise | Elements that appear after an async action |

### Setup file quick look

| File | Job |
|---|---|
| `vitest.config.ts` | Environment, aliases, globals, setup file pointer |
| `src/setupTests.ts` | DOM matchers, cleanup, browser API stubs |
| `src/utils/renderWithProviders.tsx` | Wraps components with store + router (optional but recommended) |

### The four test file types

| Test file | Tests | Key import |
|---|---|---|
| `*.test.tsx` | React component | `render, screen` from your render wrapper |
| `*.reducer.test.ts` | Redux reducer | reducer function + actions + `initialState` |
| `*.saga.test.ts` | Async side effects | `call, put` from `redux-saga/effects` + `vi` |
| `*.helper.test.ts` | Pure functions | helper function + mock data |

### Checklist for every new test file

**Component**
- [ ] `render` imported from the custom wrapper (not RTL directly)
- [ ] Component renders without throwing
- [ ] Required labels present (`getByLabelText`)
- [ ] Required buttons present (`getByRole('button', ...)`)
- [ ] Placeholder text verified (`getByPlaceholderText`)

**Reducer**
- [ ] Progress → `loading: true`, `error: null`
- [ ] Success → correct data shape, `loading: false`
- [ ] Failure → `error` string set, `data: null`
- [ ] Reset → slice back to `initialState`

**Saga**
- [ ] Step 1: dispatch progress action
- [ ] Step 2: `call()` the right API function with the right payload
- [ ] Success path: dispatch success action with mapped data
- [ ] Failure path: `iterator.throw(error)` → dispatch failure action
- [ ] Any third-party notification library mocked if called

**Helper**
- [ ] Correct output length
- [ ] First item shape matches expected
- [ ] Empty input returns empty / null / default

