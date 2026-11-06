import { API_BASE_URL } from './client';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Workflow request failed.');
  }

  return response.json();
}

export async function runWorkflow(payload) {
  return request('/api/orchestration/workflows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function fetchWorkflowStatus(workflowId) {
  return request(`/api/orchestration/workflows/${workflowId}`);
}

export async function approveWorkflow(workflowId, payload = {}) {
  return request(`/api/orchestration/workflows/${workflowId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function rejectWorkflow(workflowId, payload = {}) {
  return request(`/api/orchestration/workflows/${workflowId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function requestWorkflowChanges(workflowId, payload = {}) {
  return request(`/api/orchestration/workflows/${workflowId}/request-changes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function resumeWorkflow(workflowId) {
  return request(`/api/orchestration/workflows/${workflowId}/resume`, {
    method: 'POST',
  });
}
