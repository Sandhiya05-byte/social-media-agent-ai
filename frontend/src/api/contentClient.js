const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export async function validateContent(payload) {
  const response = await fetch(`${API_BASE_URL}/api/content/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Validation failed.');
  }

  return response.json();
}

export async function createContentItem(payload) {
  const response = await fetch(`${API_BASE_URL}/api/content`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Content creation failed.');
  }

  return response.json();
}

export async function fetchContentItems() {
  const response = await fetch(`${API_BASE_URL}/api/content`);
  if (!response.ok) {
    throw new Error('Unable to load content queue.');
  }
  return response.json();
}

export async function approveContent(contentId, notes = '', approvedBy = 'creator') {
  const response = await fetch(`${API_BASE_URL}/api/content/${contentId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved_by: approvedBy, notes }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Approval failed.');
  }

  return response.json();
}

export async function rejectContent(contentId, notes = '') {
  const response = await fetch(`${API_BASE_URL}/api/content/${contentId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Rejection failed.');
  }

  return response.json();
}

export async function requestChanges(contentId, notes = '') {
  const response = await fetch(`${API_BASE_URL}/api/content/${contentId}/request-changes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Change request failed.');
  }

  return response.json();
}

export async function scheduleContent(contentId, scheduledFor) {
  const response = await fetch(`${API_BASE_URL}/api/content/${contentId}/schedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scheduled_for: scheduledFor }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Scheduling failed.');
  }

  return response.json();
}

export async function cancelSchedule(contentId) {
  const response = await fetch(`${API_BASE_URL}/api/content/${contentId}/cancel-schedule`, {
    method: 'POST',
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Schedule cancellation failed.');
  }

  return response.json();
}

export async function rescheduleContent(contentId, scheduledFor) {
  const response = await fetch(`${API_BASE_URL}/api/content/${contentId}/reschedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scheduled_for: scheduledFor }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Rescheduling failed.');
  }

  return response.json();
}
