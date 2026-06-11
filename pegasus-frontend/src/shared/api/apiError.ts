import { AxiosError } from 'axios';

/** True for network blips / gateway timeouts during long validation polls. */
export const isTransientPollError = (error: unknown): boolean => {
  if (error instanceof AxiosError) {
    if (!error.response) return true;
    const status = error.response.status;
    return status === 408 || status === 429 || status === 502 || status === 503 || status === 504;
  }
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    return (
      msg.includes('network error')
      || msg.includes('timeout')
      || msg.includes('econnaborted')
      || msg.includes('failed to fetch')
      || msg.includes('load failed')
    );
  }
  return false;
};

export const pollRecoveryHint = (jobId: string): string =>
  ` The job may still be running on the server, but this browser lost contact with the API. `
  + `Try /validation/report/${jobId} or History once the run finishes.`;

export const getApiErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof AxiosError) {
    if (!error.response) {
      return (
        'Cannot reach the Pegasus API. The backend may have stopped or run out of memory. '
        + 'Check Docker with: docker compose ps && docker compose logs backend --tail 80'
      );
    }
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => d?.msg ?? String(d)).join(', ');
    }
    if (typeof error.response?.data?.message === 'string') {
      return error.response.data.message;
    }
    if (error.response.status === 504) {
      return 'Gateway timeout — the request took too long. The validation may still be running on the server.';
    }
  }
  if (error instanceof Error) return error.message;
  return fallback;
};
