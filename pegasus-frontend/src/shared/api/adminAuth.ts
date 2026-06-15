import { httpClient } from './httpClient';

export interface AdminAuthUser {
  email: string;
}

/** GET /admin/auth/me — requires pegasus_admin_session cookie */
export async function fetchAdminMe(): Promise<AdminAuthUser> {
  const { data } = await httpClient.get<AdminAuthUser>('/admin/auth/me');
  return data;
}

/** POST /admin/auth/login — sets pegasus_admin_session cookie on success */
export async function adminLogin(email: string, password: string): Promise<AdminAuthUser> {
  const { data } = await httpClient.post<AdminAuthUser>('/admin/auth/login', { email, password });
  return data;
}

/** POST /admin/auth/signup — first admin only; also sets session cookie */
export async function adminSignup(email: string, password: string): Promise<AdminAuthUser> {
  const { data } = await httpClient.post<AdminAuthUser>('/admin/auth/signup', { email, password });
  return data;
}

/** POST /admin/auth/logout — clears pegasus_admin_session cookie */
export async function adminLogout(): Promise<void> {
  await httpClient.post('/admin/auth/logout');
}
