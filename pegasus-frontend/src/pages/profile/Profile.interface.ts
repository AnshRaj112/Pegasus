export interface UserProfile {
  firstName: string;
  lastName: string;
  userName: string;
  email: string;
  role: string;
  assignedWorkspaces: string;
  lastLoginTime: string;
  organization: string;
  team: string;
  location: string;
  isLocal: boolean;
}

export interface AsyncState<T> {
  data: T | null;
  isFetching: boolean;
  error: string | null;
}

export interface ProfileReducerState {
  fetchProfileState: AsyncState<UserProfile>;
}
