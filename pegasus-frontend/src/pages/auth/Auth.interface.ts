export interface AuthReducerState {
  isAuthenticated: boolean;
  user: {
    fullName?: string;
    email?: string;
  } | null;
  isFetching: boolean;
  error: string | null;
}