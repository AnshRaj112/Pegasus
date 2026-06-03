import { absoluteApiUrl, fetchJson } from './http'

export async function listAdminCloudConnections() {
  return fetchJson(absoluteApiUrl('/api/v1/admin/cloud-connections'), {
    method: 'GET',
    credentials: 'include',
  })
}

export async function createAdminCloudConnection(payload) {
  return fetchJson(absoluteApiUrl('/api/v1/admin/cloud-connections'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  })
}

export async function deleteAdminCloudConnection(connectionId) {
  return fetchJson(absoluteApiUrl(`/api/v1/admin/cloud-connections/${connectionId}`), {
    method: 'DELETE',
    credentials: 'include',
  })
}
