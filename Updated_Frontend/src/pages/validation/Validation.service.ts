import  { type AxiosResponse } from 'axios';

import { type ValidationDataResponse } from './Validation.interface';

export const ValidationServiceApi = {
  submitValidation: (): Promise<AxiosResponse<ValidationDataResponse>> => {
    // Simulating a network delay of 1000ms for the validation submission
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          data: {
            jobId: 'JOB-98765-XYZ',
            status: 'Validating',
            results: null, // This will be populated later when we handle the results view
          },
          status: 200,
          statusText: 'OK',
          headers: {},
          config: {} as any,
        });
      }, 1000);
    });
  },
};