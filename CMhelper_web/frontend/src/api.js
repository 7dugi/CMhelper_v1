export const BASE_URL = import.meta.env.PROD ? "" : `http://${window.location.hostname}:8002`;
const API = `${BASE_URL}/api`;
async function req(path, opts = {}) {
  // 인증이 필요한 엔드포인트에만 토큰 추가
  if (path.startsWith('/auth/me')) {
    const token = sessionStorage.getItem('cmhelper_token');
    if (token) {
      opts.headers = { ...opts.headers, 'Authorization': `Bearer ${token}` };
    }
  }

  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// Auth
export const registerUser = (body) => req('/auth/register', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
export const loginUser    = (body) => req('/auth/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
export const getAuthMe    = ()     => req('/auth/me');

// Fields
export const getFields = (activeOnly = false) =>
  req(`/fields${activeOnly ? '?active_only=true' : ''}`);
export const createField  = (body)        => req('/fields', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
export const updateField  = (id, body)    => req(`/fields/${id}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
export const deleteField  = (id)          => req(`/fields/${id}`, { method:'DELETE' });

// Customers
export const getCustomers  = (search = '') => req(`/customers?search=${encodeURIComponent(search)}`);
export const getCustomer   = (id)           => req(`/customers/${id}`);
export const createCustomer= (body)         => req('/customers', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
export const updateCustomer= (id, body)     => req(`/customers/${id}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
export const deleteCustomer= (id)           => req(`/customers/${id}`, { method:'DELETE' });

// Consultations
export const addConsultation   = (cid, notes) =>
  req(`/customers/${cid}/consultations`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ notes }) });
export const deleteConsultation = (id) => req(`/consultations/${id}`, { method:'DELETE' });

// Excel
export const parseExcel = (file) => {
  const fd = new FormData(); fd.append('file', file);
  return req('/excel/parse', { method:'POST', body:fd });
};
export const importExcel = (file, mapping) => {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('mapping', JSON.stringify(mapping));
  return req('/excel/import', { method:'POST', body:fd });
};

// File Upload
export const uploadFile = (file) => {
  const fd = new FormData();
  fd.append('file', file);
  return req('/upload', { method:'POST', body:fd });
};

// Message Tasks
export const queueMessages = (tasks) => 
  req('/messages/queue', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(tasks) });
export const getMessageHistory = (limit=200) => req(`/messages/history?limit=${limit}`);
