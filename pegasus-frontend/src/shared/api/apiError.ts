import { AxiosError } from 'axios';

export const getApiErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => d?.msg ?? String(d)).join(', ');
    }
    if (typeof error.response?.data?.message === 'string') {
      return error.response.data.message;
    }
  }
  if (error instanceof Error) return error.message;
  return fallback;
};
