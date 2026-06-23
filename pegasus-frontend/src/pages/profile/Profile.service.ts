import { type UserProfile } from './Profile.interface';

export const fetchUserProfile = async (): Promise<UserProfile> => {
  // Replace with your actual Axios/Fetch call
  const response = await fetch('/api/user/profile');
  if (!response.ok) {
    throw new Error('Failed to fetch profile');
  }
  return response.json();
};