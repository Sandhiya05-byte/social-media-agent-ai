import { API_BASE_URL } from './client';

export async function generateCreative(payload) {
  const response = await fetch(`${API_BASE_URL}/api/creative/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Creative generation failed.');
  }

  return response.json();
}
