import request from './index'

export function list(params) {
  return request.get('/logs', { params })
}

export function get(id) {
  return request.get(`/logs/${id}`)
}
