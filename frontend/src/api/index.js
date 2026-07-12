const BASE = '/api'

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  const resp = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export const api = {
  // Config
  getConfig: () => request('/config'),
  updateConfig: (data) => request('/config', { method: 'PUT', body: JSON.stringify(data) }),

  // Cookie
  saveCookie: (cookie) => request('/cookie', { method: 'PUT', body: JSON.stringify({ cookie }) }),
  cookieStatus: () => request('/cookie/status'),

  // Sync
  triggerSync: () => request('/sync', { method: 'POST' }),

  // Bosses
  getBosses: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/bosses${q ? '?' + q : ''}`)
  },
  getBoss: (id) => request(`/bosses/${encodeURIComponent(id)}`),
  getMessages: (id, params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/bosses/${encodeURIComponent(id)}/messages${q ? '?' + q : ''}`)
  },
  updateBoss: (id, data) => request(`/bosses/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteAllBosses: () => request('/bosses', { method: 'DELETE' }),

  // Stats
  getOverview: () => request('/stats/overview'),
  getCityStats: () => request('/stats/cities'),
  getPositionStats: () => request('/stats/positions'),
  getDailyStats: () => request('/stats/daily'),
}
