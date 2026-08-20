import request from './index'

export function login(data) {
  return request.post('/auth/login', data)
}

export function me() {
  return request.get('/auth/me')
}

export function changePassword(data) {
  return request.put('/auth/password', data)
}
