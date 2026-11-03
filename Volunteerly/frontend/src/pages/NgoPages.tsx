import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { AlertTriangle, CalendarCheck, CalendarRange, CheckCircle2, Plus, Siren, UserCheck, UserX, Users } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Avatar, ChipSelect, CoverageBar, DemoBadge, Empty, EventCardView, Field, ImageUpload, Loading, PageHeader, Panel, SkillChips, StatCard, StatusBadge, selectCls } from "@/components/shared";
import { LocationPicker } from "@/components/MapView";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import { CATEGORIES, SKILLS, errMsg, fmtDate, fmtTime } from "@/lib/format";
import type { EventCard, NgoAnalytics, NgoDashboard as Dash, NgoProfile as Prof, RegistrationRow, ShiftAlert, VolunteerPublic } from "@/lib/types";

export function VolunteerDialog({ v, onClose }: { v: VolunteerPublic | null; onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <Dialog open={!!v} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="volunteer-profile-dialog">
        {v && <>
          <DialogHeader><DialogTitle className="flex items-center gap-3"><Avatar src={v.profile_image} name={v.name} size={48} />{v.name} <DemoBadge show={v.is_demo} /></DialogTitle></DialogHeader>
          <div className="space-y-3 text-sm">
            <p className="text-slate-600">{v.location} · {v.total_hours} {t("common.hours")}</p>
            <div><p className="mb-1 font-medium">{t("common.skills")}</p><SkillChips skills={v.skills} /></div>
            <div><p className="mb-1 font-medium">{t("common.interests")}</p><p className="text-slate-700">{v.interests.map((i) => t(`interests.${i}`)).join(", ") || "—"}</p></div>
            <p><span className="font-medium">{t("common.contact")}:</span> {v.phone ?? t("common.hidden")}</p>
          </div>
        </>}
      </DialogContent>
    </Dialog>
  );
}

export function RegistrationsTable({ rows, showEvent = true }: { rows: RegistrationRow[]; showEvent?: boolean }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [view, setView] = useState<VolunteerPublic | null>(null);
  const att = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "present" | "absent" }) => apiPost(`/ngo/registrations/${id}/attendance`, { attendance_status: status }),
    onSuccess: () => { toast.success(t("common.saved")); qc.invalidateQueries(); },
    onError: (e) => toast.error(errMsg(e)),
  });
  if (!rows.length) return <Empty />;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full min-w-[720px] text-sm" data-testid="registrations-table">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr><th className="p-3">{t("common.volunteers")}</th>{showEvent && <th className="p-3">{t("nav.events")}</th>}<th className="p-3">{t("common.shift")}</th><th className="p-3">{t("common.status")}</th><th className="p-3">{t("ngo.attendance")}</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-slate-100 transition-colors hover:bg-slate-50/80" data-testid={`registration-row-${r.id}`}>
              <td className="p-3">
                <button className="flex items-center gap-2 text-left" onClick={() => setView(r.volunteer)} data-testid={`view-volunteer-${r.id}`}>
                  <Avatar src={r.volunteer.profile_image} name={r.volunteer.name} size={32} />
                  <span><span className="font-medium text-slate-900 hover:text-sky-700">{r.volunteer.name}</span><span className="block text-xs text-slate-500">{r.volunteer.skills.slice(0, 3).map((s) => t(`skills.${s}`)).join(", ")}</span></span>
                </button>
              </td>
              {showEvent && <td className="p-3 text-slate-700">{r.event_title}</td>}
              <td className="p-3 text-slate-700">{fmtDate(r.shift_date)}<span className="block text-xs text-slate-500">{fmtTime(r.start_time)}–{fmtTime(r.end_time)}</span></td>
              <td className="p-3"><div className="flex flex-wrap gap-1"><StatusBadge status={r.registration_status} />{r.source !== "direct" && <StatusBadge status={r.source} />}{r.last_minute && <span className="text-xs font-semibold text-rose-700">{t("cancel.lastMinute")}</span>}</div>
                {r.replaced_by_name && <span className="text-xs text-emerald-700">{t("cancel.replacedBy", { name: r.replaced_by_name })}</span>}</td>
              <td className="p-3">
                {r.registration_status === "cancelled" ? "—" : (
                  <div className="flex items-center gap-1">
                    {r.attendance && <span className="mr-1 text-xs text-slate-600">{r.attendance.hours_contributed}h</span>}
                    <Button size="xs" variant={r.attendance?.attendance_status === "present" ? "default" : "outline"} onClick={() => att.mutate({ id: r.id, status: "present" })} data-testid={`attendance-present-${r.id}`}><UserCheck />{t("ngo.present")}</Button>
                    <Button size="xs" variant={r.attendance?.attendance_status === "absent" ? "destructive" : "outline"} onClick={() => att.mutate({ id: r.id, status: "absent" })} data-testid={`attendance-absent-${r.id}`}><UserX />{t("ngo.absent")}</Button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <VolunteerDialog v={view} onClose={() => setView(null)} />
    </div>
  );
}

export function AlertRow({ a }: { a: ShiftAlert }) {
  return (
    <Link to={`/ngo/events/${a.event_id}`} data-testid={`shift-alert-${a.shift.id}`} className="block rounded-xl border border-slate-200 p-4 transition-colors hover:border-sky-300 hover:bg-sky-50/40">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="font-medium text-slate-900">{a.emergency && <Siren className="mr-1 inline size-4 text-rose-600" />}{a.event_title}</p>
        <p className="text-xs text-slate-500">{fmtDate(a.shift.shift_date)} · {fmtTime(a.shift.start_time)}–{fmtTime(a.shift.end_time)}</p>
      </div>
      <CoverageBar c={a.shift.coverage} />
    </Link>
  );
}

export function NgoDashboard() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["ngo-dash"], queryFn: () => apiGet<Dash>("/ngo/dashboard") });
  const s = q.data?.stats;
  const v = (n?: number) => (q.isError ? "—" : n ?? "…");
  return (
    <div>
      <PageHeader title={t("dash.ngoTitle")} actions={<Link to="/ngo/events/new" className={buttonVariants()} data-testid="dashboard-create-event"><Plus />{t("event.newEvent")}</Link>} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard testId="stat-total-events" label={t("dash.totalEvents")} value={v(s?.total_events)} icon={<CalendarRange />} />
        <StatCard testId="stat-published-events" label={t("dash.publishedEvents")} value={v(s?.published_events)} icon={<CheckCircle2 />} tone="green" />
        <StatCard testId="stat-total-volunteers" label={t("dash.totalVolunteers")} value={v(s?.total_volunteers)} icon={<Users />} tone="teal" />
        <StatCard testId="stat-upcoming-events" label={t("dash.upcomingEvents")} value={v(s?.upcoming_events)} icon={<CalendarCheck />} />
        <StatCard testId="stat-total-positions" label={t("dash.totalPositions")} value={v(s?.total_positions)} icon={<Users />} />
        <StatCard testId="stat-filled-positions" label={t("dash.filledPositions")} value={v(s?.filled_positions)} icon={<UserCheck />} tone="green" />
        <StatCard testId="stat-vacant-positions" label={t("dash.vacantPositions")} value={v(s?.vacant_positions)} icon={<AlertTriangle />} tone="red" />
        <StatCard testId="stat-coverage" label={t("common.coverage")} value={s && s.total_positions ? `${Math.round((s.filled_positions / s.total_positions) * 100)}%` : "—"} icon={<CheckCircle2 />} tone="amber" />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-12">
        <Panel title={t("dash.attention")} className="lg:col-span-7" testId="attention-panel"
          action={<Link to="/ngo/cancellations" className="text-sm font-medium text-sky-700" data-testid="attention-open-manager">{t("cancel.title")} →</Link>}>
          {q.isLoading ? <Loading /> : !q.data?.attention.length ? <Empty text={t("dash.allGood")} /> : <div className="space-y-3">{q.data.attention.map((a) => <AlertRow key={a.shift.id} a={a} />)}</div>}
        </Panel>
        <Panel title={t("dash.upcomingSchedule")} className="lg:col-span-5" testId="upcoming-panel">
          {!q.data?.upcoming.length ? <Empty /> : (
            <ul className="space-y-2">{q.data.upcoming.map((e) => (
              <li key={e.id}><Link to={`/ngo/events/${e.id}`} className="flex items-center justify-between gap-2 rounded-lg p-2 hover:bg-slate-50" data-testid={`upcoming-event-${e.id}`}>
                <span><span className="font-medium text-slate-900">{e.title}</span><span className="block text-xs text-slate-500">{fmtDate(e.event_date)} · {t("event.regStats", { filled: e.total_filled, total: e.total_capacity })}</span></span>
                <StatusBadge status={e.coverage_status} /></Link></li>))}
            </ul>)}
        </Panel>
      </div>
      <Panel title={t("dash.recentRegistrations")} className="mt-6" testId="recent-registrations-panel">
        {q.data ? <RegistrationsTable rows={q.data.recent_registrations} /> : <Loading />}
      </Panel>
    </div>
  );
}

export function NgoProfile() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["ngo-profile"], queryFn: () => apiGet<Prof>("/ngo/profile") });
  const events = useQuery({ queryKey: ["ngo-events"], queryFn: () => apiGet<EventCard[]>("/ngo/events") });
  const [f, setF] = useState<Prof | null>(null);
  const form = f ?? q.data ?? null;
  const save = useMutation({ mutationFn: (p: Prof) => apiPut<Prof>("/ngo/profile", p), onSuccess: (p) => { setF(null); qc.setQueryData(["ngo-profile"], p); qc.invalidateQueries({ queryKey: ["me"] }); toast.success(t("common.saved")); }, onError: (e) => toast.error(errMsg(e)) });
  if (!form) return q.isError ? <Empty /> : <Loading />;
  const set = (patch: Partial<Prof>) => setF({ ...form, ...patch });
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={t("ngo.profileTitle")} actions={<StatusBadge status={form.verification_status} testId="ngo-verification-badge" />} />
      <Panel>
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(form); }}>
          <div className="sm:col-span-2"><ImageUpload testId="ngo-logo-upload" value={form.logo_url} onChange={(url) => set({ logo_url: url })} /></div>
          <Field label={t("auth.orgName")}><Input data-testid="ngo-name-input" value={form.organization_name} onChange={(e) => set({ organization_name: e.target.value })} /></Field>
          <Field label={t("auth.officialEmail")}><Input data-testid="ngo-email-input" value={form.contact_email} onChange={(e) => set({ contact_email: e.target.value })} /></Field>
          <Field label={t("auth.phone")}><Input data-testid="ngo-phone-input" value={form.contact_number} onChange={(e) => set({ contact_number: e.target.value })} /></Field>
          <div className="sm:col-span-2"><Field label={t("auth.description")}><Textarea data-testid="ngo-description-input" value={form.description} onChange={(e) => set({ description: e.target.value })} /></Field></div>
          <div className="sm:col-span-2"><Field label={t("auth.causes")}><ChipSelect testId="ngo-causes" ns="categories" options={CATEGORIES} value={form.causes} onChange={(v) => set({ causes: v })} /></Field></div>
          <div className="sm:col-span-2"><Field label={t("auth.location")}><LocationPicker testId="ngo-location" location={form.location} lat={form.latitude} lng={form.longitude} onChange={(v) => set(v)} /></Field></div>
          <div className="sm:col-span-2"><Button type="submit" disabled={save.isPending} data-testid="ngo-profile-save">{save.isPending ? t("common.saving") : t("common.save")}</Button></div>
        </form>
      </Panel>
      <Panel title={t("ngo.myEvents")} className="mt-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{events.data?.map((e) => <EventCardView key={e.id} ev={e} to={`/ngo/events/${e.id}`} />)}</div>
      </Panel>
    </div>
  );
}

export function NgoEvents() {
  const { t } = useTranslation();
  const [status, setStatus] = useState("");
  const q = useQuery({ queryKey: ["ngo-events"], queryFn: () => apiGet<EventCard[]>("/ngo/events") });
  const rows = (q.data ?? []).filter((e) => !status || e.status === status);
  return (
    <div>
      <PageHeader title={t("nav.events")} sub={t("event.publishHint")} actions={<>
        <select className={selectCls} value={status} onChange={(e) => setStatus(e.target.value)} data-testid="events-status-filter">
          <option value="">{t("common.all")}</option>{["draft", "published", "unpublished"].map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
        </select>
        <Link to="/ngo/events/new" className={buttonVariants()} data-testid="events-create-button"><Plus />{t("event.newEvent")}</Link></>} />
      {q.isLoading ? <Loading /> : !rows.length ? <Empty /> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{rows.map((e) => <EventCardView key={e.id} ev={e} to={`/ngo/events/${e.id}`} />)}</div>
      )}
    </div>
  );
}

export function NgoRegistrations() {
  const { t } = useTranslation();
  const [status, setStatus] = useState("");
  const q = useQuery({ queryKey: ["ngo-regs"], queryFn: () => apiGet<RegistrationRow[]>("/ngo/registrations") });
  const rows = (q.data ?? []).filter((r) => !status || r.registration_status === status);
  return (
    <div>
      <PageHeader title={t("nav.registrations")} actions={
        <select className={selectCls} value={status} onChange={(e) => setStatus(e.target.value)} data-testid="registrations-status-filter">
          <option value="">{t("common.all")}</option>{["confirmed", "cancelled", "completed", "absent"].map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
        </select>} />
      {q.isLoading ? <Loading /> : <RegistrationsTable rows={rows} />}
    </div>
  );
}

export function NgoCoverage() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["ngo-coverage"], queryFn: () => apiGet<ShiftAlert[]>("/ngo/coverage") });
  const counts = (q.data ?? []).reduce<Record<string, number>>((m, a) => ({ ...m, [a.shift.coverage.status]: (m[a.shift.coverage.status] ?? 0) + 1 }), {});
  return (
    <div>
      <PageHeader title={t("nav.coverage")} />
      <div className="mb-6 flex flex-wrap gap-3">{["critical_shortage", "partially_staffed", "fully_booked", "fully_staffed"].map((s) => (
        <div key={s} className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3" data-testid={`coverage-count-${s}`}><StatusBadge status={s} /><span className="text-xl font-bold">{counts[s] ?? 0}</span></div>))}
      </div>
      {q.isLoading ? <Loading /> : !q.data?.length ? <Empty /> : <div className="grid gap-3 lg:grid-cols-2">{q.data.map((a) => <AlertRow key={a.shift.id} a={a} />)}</div>}
    </div>
  );
}

export function NgoVolunteers() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [skill, setSkill] = useState("");
  const [view, setView] = useState<VolunteerPublic | null>(null);
  const q = useQuery({ queryKey: ["ngo-vols"], queryFn: () => apiGet<VolunteerPublic[]>("/ngo/volunteers") });
  const rows = (q.data ?? []).filter((v) => (!search || v.name.toLowerCase().includes(search.toLowerCase())) && (!skill || v.skills.includes(skill)));
  return (
    <div>
      <PageHeader title={t("nav.volunteers")} sub={t("ngo.directorySub")} actions={<>
        <Input placeholder={t("common.search")} value={search} onChange={(e) => setSearch(e.target.value)} className="w-48" data-testid="directory-search" />
        <select className={selectCls + " w-44"} value={skill} onChange={(e) => setSkill(e.target.value)} data-testid="directory-skill-filter">
          <option value="">{t("common.skills")}</option>{SKILLS.map((s) => <option key={s} value={s}>{t(`skills.${s}`)}</option>)}
        </select></>} />
      {q.isLoading ? <Loading /> : !rows.length ? <Empty /> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{rows.map((v) => (
          <button key={v.id} onClick={() => setView(v)} data-testid={`directory-volunteer-${v.id}`} className="flex gap-3 rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-md">
            <Avatar src={v.profile_image} name={v.name} size={48} />
            <div className="min-w-0 flex-1 space-y-1.5">
              <p className="flex items-center gap-2 font-semibold text-slate-900">{v.name}<DemoBadge show={v.is_demo} /></p>
              <p className="text-xs text-slate-500">{v.location} · {v.total_hours}h{v.engagements > 0 && ` · ${t("ngo.engaged", { count: v.engagements })}`}</p>
              <SkillChips skills={v.skills} />
            </div>
          </button>))}
        </div>)}
      <VolunteerDialog v={view} onClose={() => setView(null)} />
    </div>
  );
}

const COLORS = ["#0284C7", "#059669", "#0D9488", "#D97706", "#DC2626", "#6366F1", "#64748B", "#16A34A"];
const STATUS_COLORS: Record<string, string> = { fully_staffed: "#16A34A", partially_staffed: "#D97706", critical_shortage: "#DC2626", fully_booked: "#6366F1" };

export function NgoAnalyticsPage() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["ngo-analytics"], queryFn: () => apiGet<NgoAnalytics>("/ngo/analytics") });
  const a = q.data;
  if (!a) return q.isError ? <Empty /> : <Loading />;
  return (
    <div>
      <PageHeader title={t("nav.analytics")} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard testId="an-events" label={t("ngo.eventsConducted")} value={a.events_conducted} icon={<CalendarRange />} />
        <StatCard testId="an-regs" label={t("ngo.totalRegistrations")} value={a.total_registrations} icon={<Users />} tone="teal" />
        <StatCard testId="an-hours" label={t("ngo.totalHours")} value={a.total_hours} icon={<CalendarCheck />} tone="green" />
        <StatCard testId="an-coverage" label={t("ngo.avgCoverage")} value={`${a.avg_coverage}%`} icon={<CheckCircle2 />} />
        <StatCard testId="an-attendance" label={t("ngo.attendanceRate")} value={`${a.attendance_rate}%`} icon={<UserCheck />} tone="green" />
        <StatCard testId="an-cancel" label={t("ngo.cancellationRate")} value={`${a.cancellation_rate}%`} icon={<UserX />} tone="red" />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel title={t("ngo.topEvents")} testId="chart-top-events"><ResponsiveContainer width="100%" height={260}>
          <BarChart data={a.top_events} layout="vertical" margin={{ left: 20 }}><CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" /><XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="value" fill="#0284C7" radius={[0, 6, 6, 0]} /></BarChart>
        </ResponsiveContainer></Panel>
        <Panel title={t("ngo.skillShortages")} testId="chart-skill-shortages">{!a.skill_shortages.length ? <Empty /> : <ResponsiveContainer width="100%" height={260}>
          <BarChart data={a.skill_shortages.map((s) => ({ ...s, name: t(`skills.${s.name}`, { defaultValue: s.name }) }))}><CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" /><XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="value" fill="#DC2626" radius={[6, 6, 0, 0]} /></BarChart>
        </ResponsiveContainer>}</Panel>
        <Panel title={t("ngo.coverageStatus")} testId="chart-coverage-status"><ResponsiveContainer width="100%" height={240}>
          <PieChart><Pie data={a.status_split.map((s) => ({ ...s, label: t(`status.${s.name}`) }))} dataKey="value" nameKey="label" innerRadius={55} outerRadius={90} label>
            {a.status_split.map((s) => <Cell key={s.name} fill={STATUS_COLORS[s.name] ?? "#64748B"} />)}</Pie><Tooltip /></PieChart>
        </ResponsiveContainer></Panel>
        <Panel title={t("ngo.categories")} testId="chart-categories"><ResponsiveContainer width="100%" height={240}>
          <PieChart><Pie data={a.category_split.map((s) => ({ ...s, label: t(`categories.${s.name}`) }))} dataKey="value" nameKey="label" outerRadius={90} label>
            {a.category_split.map((s, i) => <Cell key={s.name} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip /></PieChart>
        </ResponsiveContainer></Panel>
      </div>
    </div>
  );
}
