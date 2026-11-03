import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { AlertCircle, CalendarCheck, CheckCircle2, Clock, Compass, Mail, MapPin, Siren, Timer, XCircle } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, ChipSelect, CoverageBar, DemoBadge, Empty, EventCardView, Field, ImageUpload, Loading, PageHeader, Panel, StatCard, StatusBadge, selectCls } from "@/components/shared";
import { LocationPicker, MapView } from "@/components/MapView";
import { NotificationItem } from "@/pages/Notifications";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import { CATEGORIES, DAYS, INTERESTS, SKILLS, SLOTS, errMsg, fmtDate, fmtDateTime, fmtTime, localized } from "@/lib/format";
import { LANGS, setLanguage } from "@/lib/i18n";
import type { EventCard, EventDetail, Invitation, Lang, MessageOut, MyRegistration, NgoPublic, VolAnalytics, VolDashboard as Dash, VolunteerProfile } from "@/lib/types";

function RegRow({ r, onCancel }: { r: MyRegistration; onCancel?: () => void }) {
  const { t } = useTranslation();
  return (
    <li data-testid={`my-registration-${r.id}`} className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center">
      <div className="min-w-0 flex-1">
        <Link to={`/volunteer/events/${r.event_id}`} className="font-semibold text-slate-900 hover:text-sky-700">{r.event_title}</Link>
        <p className="text-sm text-slate-600"><Link to={`/volunteer/ngos/${r.ngo_id}`} className="hover:underline">{r.ngo_name}</Link> · {r.event_location}</p>
        <p className="text-xs text-slate-500">{fmtDate(r.shift_date)} · {fmtTime(r.start_time)}–{fmtTime(r.end_time)} · {r.hours} {t("common.hours")}</p>
      </div>
      <div className="flex items-center gap-2">
        {r.source !== "direct" && <StatusBadge status={r.source} />}
        <StatusBadge status={r.registration_status} testId={`my-registration-status-${r.id}`} />
        {r.attendance?.attendance_status === "present" && <span className="text-xs font-semibold text-emerald-700">+{r.attendance.hours_contributed}h</span>}
        {r.can_cancel && onCancel && <Button size="sm" variant="outline" className="text-red-700" onClick={onCancel} data-testid={`cancel-registration-${r.id}`}>{t("vol.cancelReg")}</Button>}
      </div>
    </li>
  );
}

export function VolDashboard() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["vdash"], queryFn: () => apiGet<Dash>("/volunteer/dashboard") });
  const d = q.data;
  const v = (n?: number) => (q.isError ? "—" : n ?? "…");
  return (
    <div>
      <PageHeader title={t("dash.volTitle")} actions={<Link to="/volunteer/discover" className={buttonVariants()} data-testid="dashboard-discover-button"><Compass />{t("nav.discover")}</Link>} />
      {d && !d.profile_complete && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" data-testid="profile-incomplete-banner">
          <AlertCircle className="size-5 shrink-0" />{t("dash.completeProfile")}<Link to="/volunteer/profile" className="ml-auto font-semibold underline">{t("nav.profile")}</Link>
        </div>)}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard testId="vstat-hours" label={t("dash.totalHours")} value={v(d?.total_hours)} icon={<Timer />} tone="green" />
        <StatCard testId="vstat-attended" label={t("dash.eventsAttended")} value={v(d?.events_attended)} icon={<CheckCircle2 />} tone="teal" />
        <StatCard testId="vstat-upcoming" label={t("dash.upcomingShifts")} value={v(d?.upcoming.length)} icon={<CalendarCheck />} />
        <StatCard testId="vstat-invites" label={t("dash.pendingInvites")} value={v(d?.pending_invitations)} icon={<Mail />} tone="amber" />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-12">
        <Panel title={t("dash.upcomingShifts")} className="lg:col-span-7" testId="vdash-upcoming">
          {q.isLoading ? <Loading /> : !d?.upcoming.length ? <Empty /> : <ul className="space-y-2">{d.upcoming.map((r) => <RegRow key={r.id} r={r} />)}</ul>}
        </Panel>
        <Panel title={t("dash.recentNotifications")} className="lg:col-span-5" testId="vdash-notifications" action={<Link to="/volunteer/notifications" className="text-sm text-sky-700">→</Link>}>
          {!d?.recent_notifications.length ? <Empty /> : <ul className="space-y-2">{d.recent_notifications.map((n) => <NotificationItem key={n.id} n={n} />)}</ul>}
        </Panel>
      </div>
      <Panel title={`${t("dash.recommended")} · ${t("dash.available")}: ${d?.available_count ?? 0}`} className="mt-6" testId="vdash-recommended">
        {!d?.recommended.length ? <Empty /> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{d.recommended.map((e) => <EventCardView key={e.id} ev={e} to={`/volunteer/events/${e.id}`} />)}</div>}
      </Panel>
    </div>
  );
}

export function VolProfile() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["vprofile"], queryFn: () => apiGet<VolunteerProfile>("/volunteer/profile") });
  const [f, setF] = useState<VolunteerProfile | null>(null);
  const form = f ?? q.data ?? null;
  const save = useMutation({
    mutationFn: (p: VolunteerProfile) => apiPut<VolunteerProfile>("/volunteer/profile", p),
    onSuccess: (p) => { setF(null); qc.setQueryData(["vprofile"], p); qc.invalidateQueries({ queryKey: ["vdash"] }); qc.invalidateQueries({ queryKey: ["me"] }); setLanguage(p.preferred_language, false); toast.success(t("common.saved")); },
    onError: (e) => toast.error(errMsg(e)),
  });
  if (!form) return q.isError ? <Empty /> : <Loading />;
  const set = (p: Partial<VolunteerProfile>) => setF({ ...form, ...p });
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title={t("vol.profileTitle")} />
      <Panel>
        <form className="grid gap-5 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(form); }}>
          <div className="sm:col-span-2"><ImageUpload round testId="vol-image-upload" value={form.profile_image} onChange={(url) => set({ profile_image: url })} /></div>
          <Field label={t("auth.fullName")}><Input data-testid="vol-name-input" value={form.name} onChange={(e) => set({ name: e.target.value })} /></Field>
          <Field label={t("auth.phone")}><Input data-testid="vol-phone-input" value={form.phone} onChange={(e) => set({ phone: e.target.value })} /></Field>
          <div className="sm:col-span-2"><Field label={t("common.skills")}><ChipSelect testId="vol-skills" ns="skills" options={SKILLS} value={form.skills} onChange={(v) => set({ skills: v })} /></Field></div>
          <div className="sm:col-span-2"><Field label={t("common.interests")}><ChipSelect testId="vol-interests" ns="interests" options={INTERESTS} value={form.interests} onChange={(v) => set({ interests: v })} /></Field></div>
          <div className="sm:col-span-2"><Field label={t("vol.activities")}><ChipSelect testId="vol-activities" ns="categories" options={CATEGORIES} value={form.preferred_activities} onChange={(v) => set({ preferred_activities: v })} /></Field></div>
          <div className="space-y-3 rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200 sm:col-span-2">
            <p className="text-sm font-semibold text-slate-800">{t("vol.availability")}</p>
            <Field label={t("vol.days")}><ChipSelect testId="vol-days" ns="days" options={DAYS} value={form.availability.days} onChange={(v) => set({ availability: { ...form.availability, days: v } })} /></Field>
            <Field label={t("vol.slots")}><ChipSelect testId="vol-slots" ns="slots" options={SLOTS} value={form.availability.slots} onChange={(v) => set({ availability: { ...form.availability, slots: v } })} /></Field>
          </div>
          <Field label={t("auth.language")}>
            <select data-testid="vol-language-select" className={selectCls} value={form.preferred_language} onChange={(e) => set({ preferred_language: e.target.value as Lang })}>
              {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
          </Field>
          <Field label={t("vol.radius")}><Input data-testid="vol-radius-input" type="number" min={1} max={500} value={form.preferred_travel_radius} onChange={(e) => set({ preferred_travel_radius: Number(e.target.value) })} /></Field>
          <div className="sm:col-span-2"><Field label={t("vol.languagesSpoken")}><ChipSelect testId="vol-languages" ns="langs" options={LANGS.map((l) => l.code)} value={form.languages_spoken} onChange={(v) => set({ languages_spoken: v })} /></Field></div>
          <div className="sm:col-span-2"><Field label={t("common.location")}><LocationPicker testId="vol-location" location={form.location} lat={form.latitude} lng={form.longitude} onChange={(v) => set(v)} /></Field></div>
          <div className="space-y-2 rounded-xl bg-emerald-50/60 p-4 ring-1 ring-emerald-200 sm:col-span-2">
            <p className="text-sm font-semibold text-emerald-900">{t("vol.privacy")}</p>
            {(["share_location", "share_contact", "replacement_opt_in"] as const).map((k) => (
              <label key={k} className="flex items-center gap-2 text-sm text-slate-800">
                <input type="checkbox" className="size-4 accent-sky-600" data-testid={`vol-privacy-${k}`} checked={form.privacy[k]} onChange={(e) => set({ privacy: { ...form.privacy, [k]: e.target.checked } })} />
                {t({ share_location: "vol.shareLocation", share_contact: "vol.shareContact", replacement_opt_in: "vol.optIn" }[k])}
              </label>))}
          </div>
          <div className="sm:col-span-2"><Button type="submit" disabled={save.isPending} data-testid="vol-profile-save">{save.isPending ? t("common.saving") : t("common.save")}</Button></div>
        </form>
      </Panel>
    </div>
  );
}

export function Discover() {
  const { t } = useTranslation();
  const [f, setF] = useState({ q: "", category: "", location: "", date_from: "", date_to: "", skill: "" });
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  const q = useQuery({ queryKey: ["discover", qs], queryFn: () => apiGet<EventCard[]>(`/events${qs ? `?${qs}` : ""}`) });
  const set = (p: Partial<typeof f>) => setF((x) => ({ ...x, ...p }));
  const markers = (q.data ?? []).filter((e) => e.latitude != null && e.longitude != null).map((e) => ({ id: e.id, lat: e.latitude!, lng: e.longitude!, label: `${e.title} — ${e.ngo_name}`, urgent: e.emergency }));
  return (
    <div>
      <PageHeader title={t("nav.discover")} />
      <div className="mb-5 grid gap-2 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3 lg:grid-cols-6">
        <Input placeholder={`${t("common.search")}…`} value={f.q} onChange={(e) => set({ q: e.target.value })} data-testid="discover-search-input" />
        <select className={selectCls} value={f.category} onChange={(e) => set({ category: e.target.value })} data-testid="discover-category-filter">
          <option value="">{t("common.category")}: {t("common.all")}</option>{CATEGORIES.map((c) => <option key={c} value={c}>{t(`categories.${c}`)}</option>)}
        </select>
        <Input placeholder={t("common.location")} value={f.location} onChange={(e) => set({ location: e.target.value })} data-testid="discover-location-filter" />
        <select className={selectCls} value={f.skill} onChange={(e) => set({ skill: e.target.value })} data-testid="discover-skill-filter">
          <option value="">{t("common.skills")}: {t("common.all")}</option>{SKILLS.map((s) => <option key={s} value={s}>{t(`skills.${s}`)}</option>)}
        </select>
        <Input type="date" value={f.date_from} onChange={(e) => set({ date_from: e.target.value })} data-testid="discover-date-from" aria-label={t("common.from")} />
        <Input type="date" value={f.date_to} onChange={(e) => set({ date_to: e.target.value })} data-testid="discover-date-to" aria-label={t("common.to")} />
      </div>
      <div className="grid gap-6 xl:grid-cols-12">
        <div className="xl:col-span-8">
          {q.isLoading ? <Loading /> : !q.data?.length ? <Empty /> : (
            <div className="grid gap-4 sm:grid-cols-2" data-testid="discover-results">{q.data.map((e) => <EventCardView key={e.id} ev={e} to={`/volunteer/events/${e.id}`} />)}</div>)}
        </div>
        <div className="xl:col-span-4"><div className="sticky top-20"><MapView markers={markers} height={460} /></div></div>
      </div>
    </div>
  );
}

export function EventDetails() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["event", id], queryFn: () => apiGet<EventDetail>(`/events/${id}`) });
  const reg = useMutation({
    mutationFn: (shift_id: string) => apiPost<MyRegistration>("/volunteer/registrations", { shift_id }),
    onSuccess: () => { toast.success(t("status.confirmed")); qc.invalidateQueries(); },
    onError: (e) => toast.error(errMsg(e), { duration: 7000 }),
  });
  const ev = q.data;
  if (!ev) return q.isError ? <Empty /> : <Loading />;
  const { title, description } = localized(ev);
  return (
    <div>
      <div className="relative mb-6 h-56 overflow-hidden rounded-2xl bg-slate-200">
        {ev.image_url && <img src={ev.image_url} alt="" className="h-full w-full object-cover" />}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/85 to-transparent" />
        <div className="absolute bottom-0 p-6">
          <div className="mb-2 flex gap-2">{ev.emergency && <span className="vc-pulse inline-flex items-center gap-1 rounded-full bg-rose-600 px-2 py-0.5 text-xs font-semibold text-white"><Siren className="size-3" />{t("event.emergency")}</span>}
            <span className="rounded-full bg-white/90 px-2 py-0.5 text-xs font-medium">{t(`categories.${ev.category}`)}</span><DemoBadge show={ev.is_demo} /></div>
          <h1 className="text-2xl font-bold text-white sm:text-3xl" data-testid="event-detail-title">{title}</h1>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <Panel>
            <p className="whitespace-pre-line text-slate-700" data-testid="event-detail-description">{description}</p>
            <div className="mt-4 flex flex-wrap gap-4 text-sm text-slate-600">
              <span className="inline-flex items-center gap-1"><CalendarCheck className="size-4" />{fmtDate(ev.event_date)}</span>
              <span className="inline-flex items-center gap-1"><Clock className="size-4" />{fmtTime(ev.start_time)}–{fmtTime(ev.end_time)}</span>
              <span className="inline-flex items-center gap-1"><MapPin className="size-4" />{ev.location}</span>
              <span>{t("event.deadline")}: {fmtDateTime(ev.registration_deadline)}</span>
            </div>
          </Panel>
          <Panel title={t("common.shifts")} testId="event-shifts-panel">
            {!ev.registration_open && <p className="mb-3 rounded-lg bg-slate-100 p-3 text-sm text-slate-700" data-testid="registration-closed-note">{t("event.closed")}</p>}
            <ul className="space-y-3">{ev.shifts.map((s) => {
              const full = s.coverage.vacant <= 0;
              return (
                <li key={s.id} className="rounded-xl border border-slate-200 p-4" data-testid={`event-shift-${s.id}`}>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div><p className="font-semibold text-slate-900">{fmtDate(s.shift_date)} · {fmtTime(s.start_time)}–{fmtTime(s.end_time)}</p>
                      <p className="text-xs text-slate-600">{t("event.spotsLeft", { count: s.coverage.vacant })}{s.required_skills.length > 0 && ` · ${s.required_skills.map((r) => t(`skills.${r.skill}`)).join(", ")}`}</p></div>
                    {s.is_registered ? <StatusBadge status="confirmed" testId={`shift-registered-${s.id}`} /> : (
                      <Button size="sm" disabled={full || !ev.registration_open || reg.isPending} onClick={() => reg.mutate(s.id)} data-testid={`shift-register-btn-${s.id}`}>
                        {full ? t("event.full") : t("event.register")}</Button>)}
                  </div>
                  <CoverageBar c={s.coverage} />
                </li>);
            })}</ul>
          </Panel>
        </div>
        <div className="space-y-6 lg:col-span-4">
          {ev.ngo && <Panel title={t("event.organizer")}>
            <div className="flex items-center gap-3"><Avatar src={ev.ngo.logo_url} name={ev.ngo.organization_name} size={48} />
              <div><p className="font-semibold text-slate-900">{ev.ngo.organization_name}</p><StatusBadge status={ev.ngo.verification_status} /></div></div>
            <p className="mt-3 line-clamp-4 text-sm text-slate-600">{ev.ngo.description}</p>
            <Link to={`/volunteer/ngos/${ev.ngo.id}`} className="mt-3 inline-block text-sm font-semibold text-sky-700" data-testid="view-ngo-profile-link">{t("vol.viewNgo")} →</Link>
          </Panel>}
          {ev.latitude != null && ev.longitude != null && <MapView height={260} markers={[{ id: ev.id, lat: ev.latitude, lng: ev.longitude, label: ev.location, urgent: ev.emergency }]} />}
        </div>
      </div>
    </div>
  );
}

export function NgoPublicPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["ngo-public", id], queryFn: () => apiGet<NgoPublic>(`/ngos/${id}`) });
  const ev = useQuery({ queryKey: ["ngo-public-events", id], queryFn: () => apiGet<EventCard[]>(`/ngos/${id}/events`) });
  const n = q.data;
  if (!n) return q.isError ? <Empty /> : <Loading />;
  return (
    <div>
      <Panel>
        <div className="flex flex-wrap items-center gap-4"><Avatar src={n.logo_url} name={n.organization_name} size={64} />
          <div><h1 className="text-2xl font-bold text-slate-900" data-testid="ngo-public-name">{n.organization_name}</h1><p className="text-sm text-slate-600">{n.location} · {n.contact_email}</p></div>
          <div className="ml-auto flex gap-2"><StatusBadge status={n.verification_status} /><DemoBadge show={n.is_demo} /></div></div>
        <p className="mt-4 text-slate-700">{n.description}</p>
        <p className="mt-2 text-sm text-slate-600">{n.causes.map((c) => t(`categories.${c}`)).join(" · ")}</p>
      </Panel>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{ev.data?.map((e) => <EventCardView key={e.id} ev={e} to={`/volunteer/events/${e.id}`} />)}</div>
    </div>
  );
}

export function MyRegistrations() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["my-regs"], queryFn: () => apiGet<MyRegistration[]>("/volunteer/registrations") });
  const cancel = useMutation({
    mutationFn: (id: string) => apiPost<MyRegistration>(`/volunteer/registrations/${id}/cancel`),
    onSuccess: () => { toast.success(t("status.cancelled")); qc.invalidateQueries(); }, onError: (e) => toast.error(errMsg(e)),
  });
  const rows = q.data ?? [];
  const up = rows.filter((r) => r.registration_status === "confirmed");
  const past = rows.filter((r) => r.registration_status !== "confirmed");
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={t("nav.myRegistrations")} />
      {q.isLoading ? <Loading /> : <>
        <Panel title={t("vol.upcoming")} testId="my-regs-upcoming">{!up.length ? <Empty /> : <ul className="space-y-2">{up.map((r) => <RegRow key={r.id} r={r} onCancel={() => confirm(t("vol.cancelConfirm")) && cancel.mutate(r.id)} />)}</ul>}</Panel>
        <Panel title={t("vol.past")} className="mt-6" testId="my-regs-past">{!past.length ? <Empty /> : <ul className="space-y-2">{past.map((r) => <RegRow key={r.id} r={r} />)}</ul>}</Panel>
      </>}
    </div>
  );
}

export function Invitations() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["my-invites"], queryFn: () => apiGet<Invitation[]>("/volunteer/invitations") });
  const respond = useMutation({
    mutationFn: ({ id, accept }: { id: string; accept: boolean }) => apiPost<MessageOut>(`/volunteer/invitations/${id}/respond`, { accept }),
    onSuccess: (r) => { toast.success(r.message); qc.invalidateQueries(); }, onError: (e) => { toast.error(errMsg(e)); qc.invalidateQueries(); },
  });
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title={t("vol.invitationsTitle")} />
      {q.isLoading ? <Loading /> : !q.data?.length ? <Empty text={t("vol.noInvitations")} /> : (
        <ul className="space-y-3">{q.data.map((i) => (
          <li key={i.id} data-testid={`invitation-${i.id}`} className={`vc-rise rounded-xl border p-5 ${i.urgent && i.invitation_status === "pending" ? "border-rose-300 bg-rose-50/60" : "border-slate-200 bg-white"}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="flex items-center gap-2 font-semibold text-slate-900">{i.urgent && <span className="rounded bg-rose-600 px-1.5 text-[10px] font-bold uppercase text-white">{t("vol.urgent")}</span>}{i.event_title}</p>
                <p className="text-sm text-slate-600">{i.ngo_name} · {i.location}</p>
                <p className="text-sm text-slate-700">{fmtDate(i.shift_date)} · {fmtTime(i.start_time)}–{fmtTime(i.end_time)}</p>
                <p className="mt-1 text-xs text-slate-500">{i.match_score}% {t("cancel.match")} · {t("vol.expires", { time: fmtDateTime(i.expires_at) })}</p>
              </div>
              {i.invitation_status === "pending" ? (
                <div className="flex gap-2">
                  <Button onClick={() => respond.mutate({ id: i.id, accept: true })} disabled={respond.isPending} data-testid={`accept-invitation-${i.id}`}><CheckCircle2 />{t("common.accept")}</Button>
                  <Button variant="outline" onClick={() => respond.mutate({ id: i.id, accept: false })} disabled={respond.isPending} data-testid={`decline-invitation-${i.id}`}><XCircle />{t("common.decline")}</Button>
                </div>) : <StatusBadge status={i.invitation_status} testId={`invitation-status-${i.id}`} />}
            </div>
          </li>))}</ul>)}
    </div>
  );
}

const COLORS = ["#0284C7", "#059669", "#0D9488", "#D97706", "#6366F1", "#DC2626"];

export function History() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["vanalytics"], queryFn: () => apiGet<VolAnalytics>("/volunteer/analytics") });
  const a = q.data;
  if (!a) return q.isError ? <Empty /> : <Loading />;
  return (
    <div>
      <PageHeader title={t("vol.historyTitle")} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <StatCard testId="h-hours" label={t("dash.totalHours")} value={a.total_hours} icon={<Timer />} tone="green" />
        <StatCard testId="h-attended" label={t("dash.eventsAttended")} value={a.events_attended} icon={<CheckCircle2 />} tone="teal" />
        <StatCard testId="h-upcoming" label={t("vol.upcomingCommitments")} value={a.upcoming_commitments} icon={<CalendarCheck />} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Panel title={t("vol.monthlyHours")} testId="chart-monthly-hours">{!a.monthly_hours.length ? <Empty /> : <ResponsiveContainer width="100%" height={220}>
          <BarChart data={a.monthly_hours}><CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" /><XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis /><Tooltip /><Bar dataKey="value" fill="#059669" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer>}</Panel>
        <Panel title={t("vol.skillsUsed")} testId="chart-skills-used">{!a.skills_used.length ? <Empty /> : <ResponsiveContainer width="100%" height={220}>
          <BarChart data={a.skills_used.map((s) => ({ ...s, name: t(`skills.${s.name}`) }))}><CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" /><XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="value" fill="#0284C7" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer>}</Panel>
        <Panel title={t("vol.causes")} testId="chart-causes">{!a.causes_supported.length ? <Empty /> : <ResponsiveContainer width="100%" height={220}>
          <PieChart><Pie data={a.causes_supported.map((s) => ({ ...s, label: t(`categories.${s.name}`) }))} dataKey="value" nameKey="label" outerRadius={80} label>{a.causes_supported.map((s, i) => <Cell key={s.name} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer>}</Panel>
      </div>
      <Panel title={t("vol.past")} className="mt-6" testId="history-list">{!a.history.length ? <Empty /> : <ul className="space-y-2">{a.history.map((r) => <RegRow key={r.id} r={r} />)}</ul>}</Panel>
    </div>
  );
}
