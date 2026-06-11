import { absoluteApiUrl, fetchJson } from './http'

export async function adminSignup({ email, password }) {
  return fetchJson(absoluteApiUrl('/api/v1/admin/auth/signup'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  })
}

export async function adminLogin({ email, password }) {
  return fetchJson(absoluteApiUrl('/api/v1/admin/auth/login'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  })
}

export async function adminLogout() {
  return fetchJson(absoluteApiUrl('/api/v1/admin/auth/logout'), {
    method: 'POST',
    credentials: 'include',
  })
}

export async function fetchAdminMe() {
  return fetchJson(absoluteApiUrl('/api/v1/admin/auth/me'), {
    method: 'GET',
    credentials: 'include',
  })
}