import axios from 'axios';

import { PELICAN_BASE_PATH } from '../constants/service-endpoints.constants';
import { recordSessionActivity } from './sessionActivity';

const apiBase = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

export const httpClient = axios.create({
  baseURL: `${apiBase}${PELICAN_BASE_PATH}`,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // 
});

httpClient.interceptors.response.use(
  (response) => {
    recordSessionActivity(response.config.url ?? '');
    return response;
  },
  (error) => Promise.reject(error),
);
