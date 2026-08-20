import request from './index'

export function list(params) {
  return request.get('/users', { params })
}

export function create(data) {
  return request.post('/users', data)
}

export function update(id, data) {
  return request.put(`/users/${id}`, data)
}

export function remove(id) {
  return request.delete(`/users/${id}`)
}

export function grantQuota(id, data) {
  return request.post(`/users/${id}/quota`, data)
}

export function ledger(id, params) {
  return request.get(`/users/${id}/ledger`, { params })
}
