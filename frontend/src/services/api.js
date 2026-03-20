import axios from 'axios'

const rawBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'
const normalizedBase = rawBase.endsWith('/api') ? rawBase : `${rawBase.replace(/\/$/, '')}/api`

const api = axios.create({
  baseURL: normalizedBase,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default api
