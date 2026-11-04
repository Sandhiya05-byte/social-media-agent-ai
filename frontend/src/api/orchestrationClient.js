export async function runWorkflow(payload) {
  const response = await fetch('/api/orchestration/workflows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Workflow execution failed.');
  }

  return response.json();
}

export async function fetchWorkflowStatus(workflowId) {
  const response = await fetch(`/api/orchestration/workflows/${workflowId}`);

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Unable to load workflow status.');
  }

  return response.json();
}
