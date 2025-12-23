export const API_BASE_URL =
  import.meta.env.MODE === 'production'
    ? 'https://praman.info'
    : 'http://localhost:5000';

export const SSE_URL = `${API_BASE_URL}/events`;
