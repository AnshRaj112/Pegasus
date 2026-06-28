import React from 'react'
import { configureStore } from '@reduxjs/toolkit'
import { render, RenderOptions } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'

import rootReducer from '~/redux/reducer'

export * from '@testing-library/react'

type RootState = ReturnType<typeof rootReducer>

interface ExtendedRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  preloadedState?: Partial<RootState>
  route?: string
}

export const renderWithProviders = (
  ui: React.ReactElement,
  { preloadedState = {}, route = '/', ...renderOptions }: ExtendedRenderOptions = {},
) => {
  const store = configureStore({
    reducer: rootReducer,
    preloadedState,
    middleware: (getDefaultMiddleware) => getDefaultMiddleware({ thunk: false }),
  })

  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <MemoryRouter initialEntries={[route]}>
      <Provider store={store}>{children}</Provider>
    </MemoryRouter>
  )

  return { store, ...render(ui, { wrapper: Wrapper, ...renderOptions }) }
}

export { renderWithProviders as render }
