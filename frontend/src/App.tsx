import { BookOpen, Library, LayoutDashboard, Menu, Network, Presentation, Route as RouteIcon, Settings as SettingsIcon, Sigma, FileText, Users, PencilRuler } from "lucide-react";
import { useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useNetwork } from "./lib/store";
import { cn } from "./lib/utils";
import Dashboard from "./pages/Dashboard";
import Builder from "./pages/Builder";
import NetworkLibrary from "./pages/NetworkLibrary";
import Solver from "./pages/Solver";
import GraphAnalysis from "./pages/GraphAnalysis";
import Reports from "./pages/Reports";
import Team from "./pages/Team";
import Documentation from "./pages/Documentation";
import PresentationMode from "./pages/PresentationMode";
import Settings from "./pages/Settings";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/builder", label: "Create Network", icon: PencilRuler },
  { to: "/library", label: "Network Library", icon: Library },
  { to: "/solver", label: "Mathematical Solver", icon: Sigma },
  { to: "/graph", label: "Graph Analysis", icon: RouteIcon },
  { to: "/reports", label: "Solution Reports", icon: FileText },
  { to: "/team", label: "Team Contributions", icon: Users },
  { to: "/docs", label: "Project Documentation", icon: BookOpen },
  { to: "/present", label: "Presentation Mode", icon: Presentation },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function App() {
  const [open, setOpen] = useState(false);
  const { net, dirty } = useNetwork();
  const loc = useLocation();
  const fullBleed = loc.pathname === "/present";
  if (fullBleed) return <PresentationMode />;
  return (
    <div className="flex min-h-screen">
      <aside className={cn("fixed inset-y-0 left-0 z-30 flex w-64 flex-col bg-navy-900 text-slate-200 transition-transform lg:static lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-cyan2 text-white"><Network size={20} /></div>
          <div className="leading-tight"><div className="text-sm font-bold text-white">Traffic Flow</div><div className="text-xs text-cyan2-400">Network Analyzer</div></div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}
              className={({ isActive }) => cn("flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors", isActive ? "bg-brand-700 text-white" : "hover:bg-navy-800")}>
              <Icon size={17} />{label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-navy-700 px-5 py-4 text-xs text-slate-400">
          <div className="truncate font-medium text-slate-200">{net.name}</div>
          <div>{net.junctions.length} junctions · {net.roads.length} roads{dirty && <span className="ml-1 text-amber-300">· unsaved</span>}</div>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-20 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />}
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur dark:border-navy-700 dark:bg-navy-900/80 lg:hidden">
          <button aria-label="Open menu" onClick={() => setOpen(true)}><Menu /></button>
          <span className="font-semibold">Traffic Flow Network Analyzer</span>
        </header>
        <main className="fade-up mx-auto max-w-7xl p-4 sm:p-6 lg:p-8" key={loc.pathname}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/builder" element={<Builder />} />
            <Route path="/library" element={<NetworkLibrary />} />
            <Route path="/solver" element={<Solver />} />
            <Route path="/graph" element={<GraphAnalysis />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/team" element={<Team />} />
            <Route path="/docs" element={<Documentation />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
