import axios from 'axios';

const api = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('adminToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const adminAPI = {
  getConfig: () => api.get('/api/admin/config'),
  getStats: () => api.get('/api/admin/stats'),
  getMetrics: () => api.get('/api/admin/metrics'),
    // FIXED →
  getPrompts: () => api.get("/api/admin/prompts"),
  createPrompt: (data) => api.post("/api/admin/prompts", data),
  updatePrompt: (id, data) => api.put(`/api/admin/prompts/${id}`, data),
  togglePrompt: (id) => api.patch(`/api/admin/prompts/${id}/toggle`),
  deletePrompt: (id) => api.delete(`/api/admin/prompts/${id}`),
};

export default api;
