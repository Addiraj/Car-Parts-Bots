// import axios from 'axios';

// const api = axios.create({
//   baseURL: '',
//   headers: {
//     'Content-Type': 'application/json',
//   },
// });

// api.interceptors.request.use((config) => {
//   const token = localStorage.getItem('adminToken');
//   if (token) {
//     config.headers.Authorization = `Bearer ${token}`;
//   }
//   return config;
// });

// export const adminAPI = {
//   getConfig: () => api.get('/api/admin/config'),
//   getStats: () => api.get('/api/admin/stats'),
//   getMetrics: () => api.get('/api/admin/metrics'),
//     // FIXED →
//   getPrompts: () => api.get("/api/admin/prompts"),
//   createPrompt: (data) => api.post("/api/admin/prompts", data),
//   updatePrompt: (id, data) => api.put(`/api/admin/prompts/${id}`, data),
//   togglePrompt: (id) => api.patch(`/api/admin/prompts/${id}/toggle`),
//   deletePrompt: (id) => api.delete(`/api/admin/prompts/${id}`),
// };

// export default api;
// import axios from 'axios';
// import { API_BASE_URL } from '../config/api';

// const api = axios.create({
//   baseURL: API_BASE_URL,
//   headers: {
//     'Content-Type': 'application/json',
//   },
//   withCredentials: false, // important unless using cookies
// });

// api.interceptors.request.use((config) => {
//   const token = localStorage.getItem('adminToken');
//   if (token) {
//     config.headers.Authorization = `Bearer ${token}`;
//   }
//   return config;
// });

// export const adminAPI = {
//   getConfig: () => api.get('/api/admin/config'),
//   getStats: () => api.get('/api/admin/stats'),
//   getMetrics: () => api.get('/api/admin/metrics'),
//   getPrompts: () => api.get('/api/admin/prompts'),
//   createPrompt: (data) => api.post('/api/admin/prompts', data),
//   updatePrompt: (id, data) => api.put(`/api/admin/prompts/${id}`, data),
//   togglePrompt: (id) => api.patch(`/api/admin/prompts/${id}/toggle`),
//   deletePrompt: (id) => api.delete(`/api/admin/prompts/${id}`),
// };

// export default api;

import axios from 'axios';
import { API_BASE_URL } from '../config/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // 🔥 REQUIRED
});

export const adminAPI = {
  login: (data) => api.post('/api/admin/login', data),
  logout: () => api.post('/api/admin/logout'),
  getConfig: () => api.get('/api/admin/config'),
  getStats: () => api.get('/api/admin/stats'),
  getMetrics: () => api.get('/api/admin/metrics'),
  getPrompts: () => api.get('/api/admin/prompts'),
  createPrompt: (data) => api.post('/api/admin/prompts', data),
  updatePrompt: (id, data) => api.put(`/api/admin/prompts/${id}`, data),
  togglePrompt: (id) => api.patch(`/api/admin/prompts/${id}/toggle`),
  deletePrompt: (id) => api.delete(`/api/admin/prompts/${id}`),
  me: () => api.get('/api/admin/me'),

};

export default api;
