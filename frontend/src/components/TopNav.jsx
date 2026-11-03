import { Bell, Search, Settings2 } from 'lucide-react';

export function TopNav({ creatorName }) {
  return (
    <header className="flex items-center justify-between border-b border-slate-800 bg-slate-950/70 px-5 py-4 backdrop-blur">
      <div className="flex items-center gap-3 rounded-full border border-slate-700 bg-slate-900 px-3 py-2 text-slate-300 shadow-inner shadow-slate-900">
        <Search size={16} />
        <span className="text-sm">Search workflow, scripts or approvals</span>
      </div>

      <div className="flex items-center gap-3">
        <button type="button" className="rounded-full border border-slate-700 p-2 text-slate-200 shadow-sm shadow-slate-900 hover:border-slate-500">
          <Bell size={16} />
        </button>
        <button type="button" className="rounded-full border border-slate-700 p-2 text-slate-200 shadow-sm shadow-slate-900 hover:border-slate-500">
          <Settings2 size={16} />
        </button>
        <div className="flex items-center gap-3 rounded-full border border-slate-700 bg-slate-900 px-3 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-cyan-400 text-sm font-semibold text-white">
            {creatorName?.charAt(0) || 'A'}
          </div>
          <div className="hidden text-left md:block">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Creator</p>
            <p className="text-sm font-medium text-white">{creatorName || 'Alicia Moreno'}</p>
          </div>
        </div>
      </div>
    </header>
  );
}
