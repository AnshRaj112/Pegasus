import { httpClient } from './httpClient';

export interface AdminAuthUser {
  email: string;
}

export interface AdminSessionStatus {
  email: string;
  expires_at: string;
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

/** GET /admin/auth/session — current session expiry metadata */
export async function fetchAdminSessionStatus(): Promise<AdminSessionStatus> {
  const { data } = await httpClient.get<AdminSessionStatus>('/admin/auth/session');
  return data;
}

/** POST /admin/auth/extend — extend active admin session lifetime */
export async function extendAdminSession(): Promise<AdminSessionStatus> {
  const { data } = await httpClient.post<AdminSessionStatus>('/admin/auth/extend');
  return data;
}
