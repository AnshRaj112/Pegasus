import axios from 'axios';
import { PELICAN_BASE_PATH, SERVICE_ENDPOINT } from '~/shared/constants/service-endpoints.constants';
import { TestEntity } from './Test.interface';

export const TestServiceApi = {
  fetchActiveTests: () => {
    return axios.get<TestEntity[]>(`${PELICAN_BASE_PATH}${SERVICE_ENDPOINT.TESTS_ACTIVE}`);
  },
  fetchCompletedTests: () => {
    return axios.get<TestEntity[]>(`${PELICAN_BASE_PATH}${SERVICE_ENDPOINT.TESTS_COMPLETED}`);
  },
  fetchSavedTests: () => {
    return axios.get<TestEntity[]>(`${PELICAN_BASE_PATH}${SERVICE_ENDPOINT.TESTS_SAVED}`);
  },
};