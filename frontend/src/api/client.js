export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export async function fetchCreatorProfiles() {
  const response = await fetch(`${API_BASE_URL}/api/creators`);
  if (!response.ok) {
    throw new Error('Unable to load creator profiles.');
  }
  return response.json();
}

export async function createCreatorProfile(payload) {
  const response = await fetch(`${API_BASE_URL}/api/creators`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message = data.detail || 'Profile creation failed.';
    throw new Error(message);
  }

  return response.json();
}

export async function fetchDashboard() {
  const response = await fetch(`${API_BASE_URL}/api/dashboard/stats`);
  if (!response.ok) {
    throw new Error('Unable to load dashboard statistics.');
  }
  return response.json();
}

export async function fetchAgentStatus() {
  const response = await fetch(`${API_BASE_URL}/api/dashboard/agent-status`);
  if (!response.ok) {
    throw new Error('Unable to load agent status.');
  }
  return response.json();
}

export async function runResearchWorkflow(payload) {
  const response = await fetch(`${API_BASE_URL}/api/research/workflow`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message = data.detail || 'Research workflow failed.';
    throw new Error(message);
  }

  return response.json();
}
