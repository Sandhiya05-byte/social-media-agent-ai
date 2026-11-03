import {
  BarChart3,
  CalendarClock,
  Folders,
  LayoutDashboard,
  Radar,
  Settings,
  Sparkles,
  Wand2,
} from 'lucide-react';

const iconMap = {
  LayoutDashboard,
  Sparkles,
  Radar,
  Folders,
  Wand2,
  CalendarClock,
  BarChart3,
  Settings,
};

export function Sidebar({ items = [] }) {
  return (
    <aside className="hidden min-h-screen w-72 flex-col border-r border-slate-800 bg-slate-950/80 p-5 lg:flex">
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500 font-bold text-white shadow-lg shadow-violet-800/30">
          S
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-slate-400">SOCIAL</p>
          <h1 className="text-lg font-semibold text-white">Agent Suite</h1>
        </div>
      </div>

      <nav className="space-y-2">
        {items.map((item) => {
          const Icon = iconMap[item.icon] || LayoutDashboard;
          const active = item.active;

          return (
            <button
              key={item.label}
              type="button"
              className={`flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-sm font-medium transition ${
                active
                  ? 'bg-slate-800 text-white shadow-inner shadow-violet-500/10'
                  : 'text-slate-300 hover:bg-slate-900 hover:text-white'
              }`}
            >
              <span className="flex items-center gap-3">
                <Icon size={16} />
                {item.label}
              </span>
            </button>
          );
        })}
      </nav>

      <div className="mt-auto rounded-2xl border border-violet-500/30 bg-violet-500/10 p-4">
        <p className="text-xs uppercase tracking-[0.2em] text-violet-300">Approval gate</p>
        <p className="mt-2 text-sm text-slate-200">Publishing requires explicit creator approval before the schedule is released.</p>
      </div>
    </aside>
  );
}
