import { BarChart3, BookOpen, Database, Search, Server } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";

import { api } from "../lib/api";

const links = [
  { to: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { to: "/kbs", label: "Knowledge", icon: Database },
  { to: "/search", label: "Search", icon: Search },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-dify-bg text-dify-text">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="hidden w-[248px] shrink-0 border-r border-dify-border bg-dify-sidebar px-4 py-5 lg:block">
          <div className="flex items-center gap-3 px-3 py-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-dify-blueSoft text-dify-blue">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-dify-text">lite-rag</p>
              <p className="text-xs text-dify-subtext">Local knowledge workspace</p>
            </div>
          </div>

          <nav className="mt-8 space-y-1.5">
            {links.map((link, index) => {
              const Icon = link.icon;
              return (
                <NavLink
                  key={link.to}
                  to={link.to}
                  className={({ isActive }) =>
                    [
                      "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                      "animate-rise-in",
                      isActive
                        ? "bg-dify-surface text-dify-blue shadow-card"
                        : "text-dify-subtext hover:bg-dify-surface hover:text-dify-text",
                    ].join(" ")
                  }
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  <Icon className="h-4 w-4" />
                  {link.label}
                </NavLink>
              );
            })}
          </nav>

          <div className="mt-8 px-3 text-xs text-dify-softText">
            <div className="mb-1 flex items-center gap-2">
              <Server className="h-3.5 w-3.5" />
              <span>
                {location.pathname === "/search"
                  ? "检索实验页"
                  : location.pathname === "/dashboard"
                    ? "知识库总览仪表盘"
                    : "知识库总览与详情"}
              </span>
            </div>
            <p className="truncate font-mono text-[11px]">{api.baseUrl}</p>
          </div>
        </aside>

        <main className="min-w-0 flex-1 px-5 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
