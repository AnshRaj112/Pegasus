import { AxiosError, AxiosHeaders } from 'axios'

import { initializeNullState } from '~/shared/constants/common.constants'

import { UserProfile } from './Profile.interface'
import { initialState } from './Profile.reducer'

export const mockUserProfile: UserProfile = {
  firstName: 'Jane',
  lastName: 'Doe',
  userName: 'jane.doe@onixnet.com',
  email: 'jane.doe@onixnet.com',
  role: 'ADMINISTRATOR',
  assignedWorkspaces: 'PELICAN',
  lastLoginTime: '2026-06-12 11:47:03',
  organization: 'Onix',
  team: 'Platform',
  location: 'US-East',
  isLocal: true,
}

export const mockRemoteUserProfile: UserProfile = {
  ...mockUserProfile,
  firstName: 'Remote',
  lastName: 'User',
  userName: 'remote.user@onixnet.com',
  email: 'remote.user@onixnet.com',
  isLocal: false,
}

export const mockAxiosError = new AxiosError(
  'Server error',
  'ERR_BAD_REQUEST',
  undefined,
  undefined,
  {
    status: 500,
    statusText: 'Internal Server Error',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: { message: 'Failed to fetch profile' },
  },
)

export const fetchProfileLoading = {
  ...initialState,
  fetchProfileState: {
    ...initializeNullState,
    isFetching: true,
  },
}

export const fetchProfileSuccess = {
  ...initialState,
  fetchProfileState: {
    ...initializeNullState,
    data: mockUserProfile,
  },
}

export const fetchProfileError = {
  ...initialState,
  fetchProfileState: {
    ...initializeNullState,
    error: 'Failed to fetch profile',
  },
}
