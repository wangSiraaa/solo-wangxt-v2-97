// Thin fetch wrapper. Validation errors arrive as
// HTTP 400 with {detail: "中文说明"} and are surfaced verbatim.
async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(
      typeof body.detail === 'string'
        ? body.detail
        : JSON.stringify(body.detail ?? body)
    );
  }
  return body;
}

export const api = {
  fit: (payload) => request('/api/fit', { method: 'POST', body: JSON.stringify(payload) }),
  save: (payload) => request('/api/analyses', { method: 'POST', body: JSON.stringify(payload) }),
  list: () => request('/api/analyses'),
  get: (id) => request(`/api/analyses/${id}`),
  refit: (id) => request(`/api/analyses/${id}/refit`, { method: 'POST' }),
};
