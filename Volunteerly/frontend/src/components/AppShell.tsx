import { useState } from "react";
import { Link, Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  BarChart3, Bell, CalendarRange, ClipboardList, Compass, HandHeart, History, LayoutDashboard, LogOut, Mail, Menu,
  ShieldAlert, Building2, UserRound, Users, Activity,
} from "lucide-react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api";
import { LANGS, setLanguage } from "@/lib/i18n";
import { endSession, homeFor, useMe } from "@/lib/session";
import type { Notification, Role } from "@/lib/types";
import { Loading } from "@/components/shared";
import { useLiveSync, useNewNotificationToasts } from "@/lib/live";
import { cn } from "@/lib/utils";

const NAV: Record<Role, { to: string; key: string; icon: typeof Bell }[]> = {
  ngo: [
    { to: "/ngo/dashboard", key: "dashboard", icon: LayoutDashboard },
    { to: "/ngo/events", key: "events", icon: CalendarRange },
    { to: "/ngo/registrations", key: "registrations", icon: ClipboardList },
    { to: "/ngo/coverage", key: "coverage", icon: Activity },
    { to: "/ngo/cancellations", key: "cancellations", icon: ShieldAlert },
    { to: "/ngo/volunteers", key: "volunteers", icon: Users },
    { to: "/ngo/analytics", key: "analytics", icon: BarChart3 },
    { to: "/ngo/notifications", key: "notifications", icon: Bell },
    { to: "/ngo/profile", key: "profile", icon: Building2 },
  ],
  volunteer: [
    { to: "/volunteer/dashboard", key: "dashboard", icon: LayoutDashboard },
    { to: "/volunteer/discover", key: "discover", icon: Compass },
    { to: "/volunteer/registrations", key: "myRegistrations", icon: ClipboardList },
    { to: "/volunteer/invitations", key: "invitations", icon: Mail },
    { to: "/volunteer/history", key: "history", icon: History },
    { to: "/volunteer/notifications", key: "notifications", icon: Bell },
    { to: "/volunteer/profile", key: "profile", icon: UserRound },
  ],
};

export function LanguageSwitcher({ dark }: { dark?: boolean }) {
  const { i18n, t } = useTranslation();
  const { data: me } = useMe();
  return (
    <select aria-label={t("nav.language")} data-testid="language-selector" value={i18n.language}
      onChange={(e) => setLanguage(e.target.value, !!me)}
      className={cn("h-9 rounded-lg border px-2 text-sm font-medium focus-visible:ring-2 focus-visible:ring-sky-500",
        dark ? "border-white/20 bg-white/10 text-white" : "border-slate-300 bg-white text-slate-800")}>
      {LANGS.map((l) => <option key={l.code} value={l.code} className="text-slate-900">{l.label}</option>)}
    </select>
  );
}

function SideNav({ role, onNav }: { role: Role; onNav?: () => void }) {
  const { t } = useTranslation();
  return (
    <nav className="flex flex-col gap-1 px-3">
      {NAV[role].map(({ to, key, icon: Icon }) => (
        <NavLink key={to} to={to} onClick={onNav} data-testid={`nav-${key}`}
          className={({ isActive }) => cn("flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-150",
            isActive ? "bg-sky-500/15 text-sky-300" : "text-slate-300 hover:bg-slate-800 hover:text-white")}>
          <Icon className="size-4" />{t(`nav.${key}`)}
        </NavLink>
      ))}
    </nav>
  );
}

export default function AppShell({ role }: { role: Role }) {
  const { t } = useTranslation();
  const nav = useNavigate();
  const { data: me, isLoading, isError } = useMe();
  const [open, setOpen] = useState(false);
  const notes = useQuery({ queryKey: ["notifications"], queryFn: () => apiGet<Notification[]>("/notifications"), enabled: !!me && me.role === role });
  const live = useLiveSync(!!me && me.role === role);
  useNewNotificationToasts(notes.data);
  if (isLoading) return <div className="p-8"><Loading /></div>;
  if (isError || !me) return <Navigate to="/login" replace />;
  if (me.role !== role) return <Navigate to={homeFor(me)} replace />;
  const unread = (notes.data ?? []).filter((n) => !n.read_status).length;
  const brand = (
    <Link to={homeFor(me)} className="flex items-center gap-2 px-6 py-5 text-white" data-testid="brand-link">
      <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-sky-500 to-emerald-500"><HandHeart className="size-5" /></span>
      <span className="text-lg font-bold tracking-tight">{t("brand")}</span>
    </Link>
  );
  async function logout() { await endSession(); nav("/login"); }
  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col bg-slate-900 lg:flex">
        {brand}
        <p className="px-6 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">{role === "ngo" ? "NGO" : t("common.volunteers")}</p>
        <SideNav role={role} />
        <div className="mt-auto border-t border-slate-800 p-4">
          <button onClick={logout} data-testid="logout-button" className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-800 hover:text-white"><LogOut className="size-4" />{t("nav.logout")}</button>
        </div>
      </aside>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-64 bg-slate-900 p-0 text-white">
          <SheetTitle className="sr-only">Menu</SheetTitle>
          {brand}<SideNav role={role} onNav={() => setOpen(false)} />
          <button onClick={logout} data-testid="mobile-logout-button" className="m-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"><LogOut className="size-4" />{t("nav.logout")}</button>
        </SheetContent>
      </Sheet>
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur-md sm:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setOpen(true)} data-testid="mobile-menu-button"><Menu /></Button>
          <div className="min-w-0 flex-1 truncate text-sm text-slate-600">
            <span className="font-semibold text-slate-900" data-testid="topbar-user-name">{me.full_name}</span>
            {me.is_demo && <span className="ml-2 rounded bg-violet-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-violet-700">{t("common.demo")}</span>}
          </div>
          <span data-testid="live-indicator" title={t("common.liveHint")}
            className={cn("hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold sm:inline-flex",
              live.connected ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200" : "bg-slate-100 text-slate-500")}>
            <span className={cn("size-2 rounded-full", live.connected ? "animate-pulse bg-emerald-500" : "bg-slate-400")} />{t("common.live")}
          </span>
          <LanguageSwitcher />
          <Link to={`/${role}/notifications`} data-testid="topbar-notifications-link" className="relative grid size-9 place-items-center rounded-lg text-slate-700 transition-colors hover:bg-slate-100">
            <Bell className="size-5" />
            {unread > 0 && <span data-testid="unread-count" className="absolute -right-0.5 -top-0.5 grid min-w-5 place-items-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">{unread}</span>}
          </Link>
        </header>
        <main className="p-4 sm:p-6 lg:p-8"><Outlet /></main>
      </div>
    </div>
  );
}
