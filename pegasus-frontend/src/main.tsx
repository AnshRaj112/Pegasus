import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider } from 'antd';
import { Provider } from 'react-redux';

import { store } from './redux/store.ts';

import App from './App.tsx';

import './styles/tokens.css';  // ⚡ MAKE SURE THIS IS HERE!
import './index.css';          // ⚡ MAKE SURE THIS IS HERE!

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider>
      <Provider store={store}>
        {/* ModalProvider will go here once implemented */}
        <App />
      </Provider>
    </ConfigProvider>
  </React.StrictMode>
);