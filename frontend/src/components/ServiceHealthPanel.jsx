import { useCallback, useEffect, useState } from 'react';
import { Activity, AlertCircle, CheckCircle2, Loader2, XCircle } from 'lucide-react';

const BROWSER_SERVICE_URL = import.meta.env.VITE_BROWSER_SERVICE_URL || 'http://127.0.0.1:8002';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

async function probeUrl(url, timeoutMs = 4000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(id);
    if (!res.ok) return { status: 'error', detail: `HTTP ${res.status}` };
    const json = await res.json().catch(() => ({}));
    return { status: 'healthy', detail: json };
  } catch (err) {
    clearTimeout(id);
    if (err.name === 'AbortError') return { status: 'unavailable', detail: 'Timeout' };
    return { status: 'unavailable', detail: err.message };
  }
}

async function fetchAllHealth() {
  const [frontend, backend, browserSvc, ollamaRaw] = await Promise.allSettled([
    // Frontend is always reachable if this JS is running
    Promise.resolve({ status: 'healthy', detail: { service: 'frontend' } }),
    probeUrl(`${API_BASE_URL}/api/health`),
    probeUrl(`${BROWSER_SERVICE_URL}/health`),
    probeUrl('http://127.0.0.1:11434/api/tags'),
  ]);

  const resolve = (settled) =>
    settled.status === 'fulfilled' ? settled.value : { status: 'unavailable', detail: settled.reason?.message };

  const backendResult = resolve(backend);
  const browserResult = resolve(browserSvc);
  const ollamaResult = resolve(ollamaRaw);

  // Parse active Ollama model from /api/tags
  let ollamaModel = null;
  if (ollamaResult.status === 'healthy' && ollamaResult.detail?.models?.length > 0) {
    ollamaModel = ollamaResult.detail.models[0].name;
  }

  return {
    frontend: resolve(frontend),
    backend: backendResult,
    browserService: browserResult,
    ollama: ollamaResult,
    ollamaModel,
  };
}

const statusConfig = {
  healthy: {
    icon: CheckCircle2,
    color: 'text-emerald-400',
    dot: 'bg-emerald-400',
    badge: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    label: 'Healthy',
  },
  error: {
    icon: AlertCircle,
    color: 'text-amber-400',
    dot: 'bg-amber-400',
    badge: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    label: 'Error',
  },
  unavailable: {
    icon: XCircle,
    color: 'text-red-400',
    dot: 'bg-red-400',
    badge: 'border-red-500/30 bg-red-500/10 text-red-300',
    label: 'Unavailable',
  },
  checking: {
    icon: Loader2,
    color: 'text-slate-400',
    dot: 'bg-slate-500',
    badge: 'border-slate-700 bg-slate-800 text-slate-400',
    label: 'Checking…',
  },
};

function ServiceRow({ name, status, detail }) {
  const cfg = statusConfig[status] ?? statusConfig.checking;
  const Icon = cfg.icon;
  const isLoading = status === 'checking';

  return (
    <div className="flex items-center justify-between gap-3 py-2.5 border-b border-slate-800/60 last:border-0">
      <div className="flex items-center gap-2.5 min-w-0">
        <span className={`h-2 w-2 flex-shrink-0 rounded-full ${cfg.dot} ${isLoading ? 'animate-pulse' : ''}`} />
        <span className="text-sm font-medium text-slate-200 truncate">{name}</span>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {detail && status !== 'healthy' && (
          <span className="hidden text-xs text-slate-500 md:inline truncate max-w-[140px]">{detail}</span>
        )}
        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${cfg.badge}`}>
          <Icon size={10} className={isLoading ? 'animate-spin' : ''} />
          {cfg.label}
        </span>
      </div>
    </div>
  );
}

export function ServiceHealthPanel() {
  const [health, setHealth] = useState(null);
  const [lastChecked, setLastChecked] = useState(null);
  const [checking, setChecking] = useState(false);

  const refresh = useCallback(async () => {
    setChecking(true);
    const result = await fetchAllHealth();
    setHealth(result);
    setLastChecked(new Date());
    setChecking(false);
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30_000);
    return () => clearInterval(interval);
  }, [refresh]);

  const rows = health
    ? [
        { name: 'Frontend (React)', status: health.frontend.status, detail: null },
        { name: 'Backend (FastAPI :8001)', status: health.backend.status, detail: typeof health.backend.detail === 'string' ? health.backend.detail : null },
        { name: 'Browser Service (:8002)', status: health.browserService.status, detail: typeof health.browserService.detail === 'string' ? health.browserService.detail : null },
        { name: `Ollama${health.ollamaModel ? ` · ${health.ollamaModel}` : ''}`, status: health.ollama.status, detail: typeof health.ollama.detail === 'string' ? health.ollama.detail : null },
      ]
    : [
        { name: 'Frontend (React)', status: 'checking' },
        { name: 'Backend (FastAPI :8001)', status: 'checking' },
        { name: 'Browser Service (:8002)', status: 'checking' },
        { name: 'Ollama', status: 'checking' },
      ];

  const allHealthy = health && Object.entries(health)
    .filter(([k]) => ['frontend', 'backend', 'browserService', 'ollama'].includes(k))
    .every(([, v]) => v.status === 'healthy');

  return (
    <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-violet-400" />
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Infrastructure</p>
            <h3 className="mt-0.5 text-lg font-semibold text-white">Service health</h3>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {lastChecked && (
            <span className="hidden text-[10px] text-slate-500 md:inline">
              {lastChecked.toLocaleTimeString()}
            </span>
          )}
          <button
            type="button"
            onClick={refresh}
            disabled={checking}
            className="rounded-full border border-slate-700 px-3 py-1 text-xs font-medium text-slate-300 hover:border-slate-500 disabled:opacity-50"
          >
            {checking ? 'Checking…' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="divide-y divide-transparent">
        {rows.map((row) => (
          <ServiceRow key={row.name} {...row} />
        ))}
      </div>

      {health && (
        <div className={`mt-4 rounded-xl border px-3 py-2 text-xs font-medium ${
          allHealthy
            ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-300'
            : 'border-amber-500/20 bg-amber-500/5 text-amber-300'
        }`}>
          {allHealthy
            ? '✓ All services operational — ready for end-to-end workflow'
            : '⚠ One or more services unreachable — check startup logs'}
        </div>
      )}
    </div>
  );
}
