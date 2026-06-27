import { AxiosError, InternalAxiosRequestConfig } from 'axios';

import { httpClient } from '~/shared/api/httpClient';
import { PATHS } from '~/router/router.constants';

const pendingGetRequests = new Map<string, AbortController>();

const isAuthEndpoint = (url?: string): boolean =>
  Boolean(url?.includes('/admin/auth/'));

const buildGetRequestKey = (config: InternalAxiosRequestConfig): string => {
  const params = config.params ? JSON.stringify(config.params) : '';
  return `${config.method ?? 'get'}:${config.baseURL ?? ''}${config.url ?? ''}:${params}`;
};

const redirectToLogin = (): void => {
  if (typeof window === 'undefined') return;
  const currentPath = window.location.hash.replace(/^#/, '') || PATHS.DASHBOARD;
  if (currentPath.startsWith(PATHS.LOGIN)) return;
  window.location.hash = `#${PATHS.LOGIN}`;
};

export const setupAxiosInterceptors = (): void => {
  httpClient.interceptors.request.use((config) => {
    config.headers.set('X-Request-ID', crypto.randomUUID());

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    if (csrfToken) {
      config.headers.set('X-CSRF-Token', csrfToken);
    }

    if (config.method?.toLowerCase() === 'get') {
      const requestKey = buildGetRequestKey(config);
      const existing = pendingGetRequests.get(requestKey);
      if (existing) {
        existing.abort();
      }

      const controller = new AbortController();
      pendingGetRequests.set(requestKey, controller);
      config.signal = controller.signal;
    }

    return config;
  });

  httpClient.interceptors.response.use(
    (response) => {
      if (response.config.method?.toLowerCase() === 'get') {
        pendingGetRequests.delete(buildGetRequestKey(response.config));
      }
      return response;
    },
    (error: AxiosError) => {
      if (error.config?.method?.toLowerCase() === 'get') {
        pendingGetRequests.delete(buildGetRequestKey(error.config));
      }

      const status = error.response?.status;
      const requestUrl = error.config?.url;

      if ((status === 401 || status === 403) && !isAuthEndpoint(requestUrl)) {
        redirectToLogin();
      }

      return Promise.reject(error);
    },
  );
};

setupAxiosInterceptors();
