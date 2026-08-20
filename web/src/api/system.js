import request from './index'

export function getSettings() {
  return request.get('/system/settings')
}

export function updateSettings(data) {
  return request.put('/system/settings', data)
}

export function health() {
  return request.get('/system/health')
}
