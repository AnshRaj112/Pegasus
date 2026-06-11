export interface AuthReducerState {
  isAuthenticated: boolean;
  user: {
    fullName?: string;
    email?: string;
  } | null;
  isLoading: boolean;
  error: string | null;
}