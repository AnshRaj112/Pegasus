import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider } from 'antd';
import { Provider } from 'react-redux';
import 'bootstrap/dist/css/bootstrap-utilities.min.css';
import { store } from './redux/store.ts';
import './axios-interceptor.ts';

import App from './App.tsx';

import '~/assets/styles/global.scss';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider theme={{ token: { fontFamily: 'Plus Jakarta Sans, sans-serif' } }}>
      <Provider store={store}>
        {/* ModalProvider will go here once implemented */}
        <App />
      </Provider>
    </ConfigProvider>
  </React.StrictMode>
);