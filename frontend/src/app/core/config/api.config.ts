const localHosts = new Set(['localhost', '127.0.0.1', '::1']);

const apiBaseUrl = typeof window !== 'undefined' && localHosts.has(window.location.hostname)
  ? 'http://127.0.0.1:8000/api'
  : '/api';

export const apiConfig = {
  baseUrl: apiBaseUrl,
} as const;
