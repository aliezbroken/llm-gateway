import request from './index'

export function overview(params) {
  return request.get('/stats/overview', { params })
}

export function trend(params) {
  return request.get('/stats/trend', { params })
}

export function latency(params) {
  return request.get('/stats/latency', { params })
}

export function distribution(params) {
  return request.get('/stats/distribution', { params })
}
