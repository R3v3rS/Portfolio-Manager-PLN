import axios from 'axios';

const api = axios.create({
  baseURL: '/api/portfolio',
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;
