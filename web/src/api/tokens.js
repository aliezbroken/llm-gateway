import request from './index'

export function list(params) {
  return request.get('/tokens', { params })
}

export function create(data) {
  return request.post('/tokens', data)
}

export function update(id, data) {
  return request.put(`/tokens/${id}`, data)
}

export function remove(id) {
  return request.delete(`/tokens/${id}`)
}

export function usage(id) {
  return request.get(`/tokens/${id}/usage`)
}
