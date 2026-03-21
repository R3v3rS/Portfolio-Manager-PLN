import axios from 'axios';
import { extractErrorMessage, extractPayload } from './apiEnvelope';

const api = axios.create({
  baseURL: '/api/portfolio',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => {
    response.data = extractPayload(response.data);
    return response;
  },
  (error) => {
    if (error?.response?.data) {
      const details =
        typeof error.response.data === 'object' && error.response.data?.error?.details !== undefined
          ? error.response.data.error.details
          : undefined;
      const message = extractErrorMessage(error.response.data, error.message);
      error.response.data = {
        ...error.response.data,
        error: message,
        details,
      };
      error.message = message;
    }
    return Promise.reject(error);
  }
);

export default api;
