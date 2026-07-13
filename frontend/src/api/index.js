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
  generateMessage: async (data, onChunk) => {
    const resp = await fetch('/api/messenger/generate-message', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    // 如果是 SSE 流（AI 模式），逐块回调
    const ct = resp.headers.get('content-type') || ''
    if (ct.includes('text/event-stream') && onChunk) {
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let result = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const d = JSON.parse(line.slice(6))
            if (d.done) return result
            if (d.chunk) { result += d.chunk; onChunk(result) }
          }
        }
      }
      return result
    }
    // 非流式（固定模板），直接返回 JSON
    const r = await resp.json()
    return r.message
  },

  // Cookie
  saveCookie: (cookie) => request('/cookie', { method: 'PUT', body: JSON.stringify({ cookie }) }),
  cookieStatus: () => request('/cookie/status'),
  verifyCookie: () => request('/cookie/verify'),

  // Sync
  triggerSync: () => fetch('/api/sync', { method: 'POST' }),
  getSyncLogs: () => request('/sync/logs?limit=10'),

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
  loginAndCapture: () => request('/messenger/login', { method: 'POST' }),
  checkMessengerLogin: () => request('/messenger/check-login'),
  importCookies: (jsonStr) => request('/messenger/import-cookies', { method: 'POST', body: JSON.stringify({ data: jsonStr }) }),
  sendMessage: (data) => request('/messenger/send', { method: 'POST', body: JSON.stringify(data) }),
  sendBatchMessage: (data) => request('/messenger/send-batch', { method: 'POST', body: JSON.stringify(data) }),
  deleteAllBosses: () => request('/bosses', { method: 'DELETE' }),

  // Reminders
  getReminders: (params) => {
    const q = new URLSearchParams(params).toString()
    return request(`/reminders${q ? '?' + q : ''}`)
  },
  previewReminders: (data) => request('/reminders/preview', { method: 'POST', body: JSON.stringify(data) }),
  sendReminders: (data) => request('/reminders/send', { method: 'POST', body: JSON.stringify(data) }),
  sendRemindersWithMessages: (data) => request('/reminders/send-messages', { method: 'POST', body: JSON.stringify(data) }),

  // Stats
  getOverview: () => request('/stats/overview'),
  getCityStats: () => request('/stats/cities'),
  getPositionStats: () => request('/stats/positions'),
  getDailyStats: () => request('/stats/daily'),
  getRecentResumes: () => request('/stats/recent-resumes?limit=5'),
  getDashboardSyncLogs: () => request('/stats/sync-logs?limit=5'),
  generateReport: (type) => request(`/reports/${type}`),
  listReports: () => request('/reports/list'),
}
