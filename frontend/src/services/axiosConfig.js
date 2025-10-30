// src/services/axiosConfig.js
import axios from 'axios';

// Create axios instance with base URL from environment variable
const api = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;