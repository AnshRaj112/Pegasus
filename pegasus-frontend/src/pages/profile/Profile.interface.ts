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

export interface ProfileState {
  data: UserProfile | null;
  isLoading: boolean;
  error: string | null;
}