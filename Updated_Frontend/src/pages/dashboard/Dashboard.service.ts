import axios, { type AxiosResponse } from 'axios';

import { type DashboardDataResponse } from './Dashboard.interface';
import { mockDashboardData } from './Dashboard.mockData';

export const DashboardServiceApi = {
  fetchDashboardData: (): Promise<AxiosResponse<DashboardDataResponse>> => {
    // Simulating a network delay of 500ms, then returning our mock data
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          data: mockDashboardData,
          status: 200,
          statusText: 'OK',
          headers: {},
          config: {} as any,
        });
      }, 500);
    });
  },
};