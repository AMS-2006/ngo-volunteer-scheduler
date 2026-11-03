import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { MapPin, Search, Send, Siren, Sparkles, UserMinus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Avatar, CoverageBar, DemoBadge, Empty, Loading, PageHeader, Panel, SkillChips, StatusBadge } from "@/components/shared";
import { apiGet, apiPost } from "@/lib/api";
import { errMsg, fmtDate, fmtDateTime, fmtTime } from "@/lib/format";
import type { CancellationOverview, CandidatesOut, InvitationRow, InviteOut, ShiftWithCoverage } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Target { shiftId: string; regId: string | null; title: string }

function ScoreRing({ score }: { score: number }) {
  const deg = Math.round((score / 100) * 360);
  const color = score >= 85 ? "#059669" : score >= 65 ? "#0284C7" : "#D97706";
  return (
    <div className="grid size-16 shrink-0 place-items-center rounded-full" style={{ background: `conic-gradient(${color} ${deg}deg, #E2E8F0 0)` }}>
      <div className="grid size-12 place-items-center rounded-full bg-white text-sm font-bold text-slate-900">{Math.round(score)}%</div>
    </div>
  );
}

function Candidates({ target }: { target: Target }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [sel, setSel] = useState<string[]>([]);
  const q = useQuery({
    queryKey: ["candidates", target.shiftId, target.regId],
    queryFn: () => apiGet<CandidatesOut>(`/ngo/shifts/${target.shiftId}/candidates${target.regId ? `?registration_id=${target.regId}` : ""}`),
  });
  const inv = useQuery({ queryKey: ["shift-invites", target.shiftId], queryFn: () => apiGet<InvitationRow[]>(`/ngo/shifts/${target.shiftId}/invitations`) });
  const send = useMutation({
    mutationFn: (ids: string[]) => apiPost<InviteOut>("/ngo/invitations", { shift_id: target.shiftId, cancelled_registration_id: target.regId, volunteer_ids: ids }),
    onSuccess: (r) => { toast.success(r.message); setSel([]); qc.invalidateQueries(); },
    onError: (e) => toast.error(errMsg(e)),
  });
  if (q.isLoading) return <Loading />;
  if (!q.data) return <Empty />;
  const d = q.data;
  return (
    <div className="space-y-4" data-testid="candidates-panel">
      <div className="rounded-xl bg-sky-50 p-4 ring-1 ring-sky-200">
        <p className="text-sm font-semibold text-sky-900">{d.event_title} · {fmtDate(d.shift.shift_date)} {fmtTime(d.shift.start_time)}–{fmtTime(d.shift.end_time)}</p>
        <p className="mt-1 text-sm text-sky-800" data-testid="target-skills">{t("cancel.targetSkills")}: <b>{d.target_skills.map((s) => t(`skills.${s}`)).join(", ") || "—"}</b></p>
        <div className="mt-3"><CoverageBar c={d.shift.coverage} testId="candidates-shift-coverage" /></div>
        {Object.keys(d.excluded).length > 0 && (
          <p className="mt-2 text-xs text-slate-600" data-testid="excluded-summary">{t("cancel.excluded")}: {Object.entries(d.excluded).map(([k, v]) => `${t(`cancel.reasons.${k}`)} (${v})`).join(" · ")}</p>
        )}
      </div>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-900">{t("cancel.candidates")} ({d.candidates.length})</h3>
        <Button size="sm" disabled={!sel.length || send.isPending} onClick={() => send.mutate(sel)} data-testid="invite-selected-button"><Send />{t("cancel.inviteSelected", { count: sel.length })}</Button>
      </div>
      {!d.candidates.length ? <Empty text={t("cancel.noCandidates")} /> : (
        <ol className="space-y-3">
          {d.candidates.map((c, i) => {
            const vid = c.volunteer.id;
            const invited = c.invitation_status === "pending" || c.invitation_status === "accepted";
            return (
              <li key={vid} data-testid={`candidate-card-${vid}`} className="vc-rise flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 transition-[border-color,box-shadow] duration-200 hover:border-sky-300 hover:shadow-sm sm:flex-row sm:items-center" style={{ animationDelay: `${i * 40}ms` }}>
                <Checkbox checked={sel.includes(vid)} disabled={invited} onCheckedChange={(on) => setSel((s) => (on ? [...s, vid] : s.filter((x) => x !== vid)))} data-testid={`candidate-select-${vid}`} />
                <span className="w-6 text-sm font-bold text-slate-400">#{i + 1}</span>
                <Avatar src={c.volunteer.profile_image} name={c.volunteer.name} size={44} />
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="flex flex-wrap items-center gap-2 font-semibold text-slate-900" data-testid={`candidate-name-${vid}`}>{c.volunteer.name}<DemoBadge show={c.volunteer.is_demo} /></p>
                  <p className="flex flex-wrap gap-x-3 text-xs text-slate-600">
                    <span className="inline-flex items-center gap-1"><MapPin className="size-3" />{c.distance_km != null ? `${c.distance_km} ${t("common.km")}` : t("common.distanceUnavailable")}</span>
                    <span>{t("cancel.availability")}: {c.availability_pct}%</span>
                    <span>{t("cancel.recent", { hours: c.recent_hours, count: c.upcoming_commitments })}</span>
                  </p>
                  <SkillChips skills={c.volunteer.skills} highlight={c.matched_skills} />
                  <p className="text-[11px] text-slate-500" data-testid={`candidate-breakdown-${vid}`}>
                    {t("common.skills")} {c.breakdown.skills}/40 · {t("cancel.availability")} {c.breakdown.availability}/30 · {t("common.location")} {c.breakdown.distance}/20 · {t("common.interests")} {c.breakdown.interests}/10 · {t("cancel.fairness")} {c.breakdown.fairness_adjustment}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <div data-testid={`candidate-score-${vid}`}><ScoreRing score={c.score} /></div>
                  {c.invitation_status ? <StatusBadge status={c.invitation_status} testId={`candidate-invite-status-${vid}`} />
                    : <Button size="sm" variant="outline" disabled={send.isPending} onClick={() => send.mutate([vid])} data-testid={`invite-candidate-btn-${vid}`}><Send />{t("cancel.invite")}</Button>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
      <Panel title={t("cancel.inviteTracking")} testId="invite-tracking-panel">
        <p className="mb-2 text-xs text-slate-500" data-testid="invite-expiry-rule">{t("cancel.expiryRule")}</p>
        {!inv.data?.length ? <Empty /> : (
          <ul className="divide-y divide-slate-100">{inv.data.map((i) => (
            <li key={i.id} className="flex items-center justify-between gap-2 py-2 text-sm" data-testid={`invite-row-${i.id}`}>
              <span>{i.urgent && <Siren className="mr-1 inline size-3.5 text-rose-600" />}{i.volunteer_name} · {i.match_score}% · <span className="text-slate-500">{fmtDateTime(i.created_at)}</span>
                {i.invitation_status === "pending" && i.expires_at && <span className="text-slate-500"> → {fmtDateTime(i.expires_at)}</span>}
                {i.auto_forwarded && <span className="ml-2 rounded bg-teal-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-teal-700 ring-1 ring-teal-200" data-testid={`invite-auto-${i.id}`}>{t("cancel.autoForwarded")}</span>}</span>
              <StatusBadge status={i.invitation_status} />
            </li>))}</ul>)}
      </Panel>
    </div>
  );
}

function Emergency({ shift, title }: { shift: ShiftWithCoverage; title: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [needed, setNeeded] = useState(Math.max(1, shift.coverage.vacant));
  const m = useMutation({
    mutationFn: () => apiPost<InviteOut>("/ngo/emergency", { shift_id: shift.id, needed }),
    onSuccess: (r) => { toast.success(r.message); qc.invalidateQueries(); }, onError: (e) => toast.error(errMsg(e)),
  });
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg bg-rose-50 p-3 ring-1 ring-rose-200" data-testid={`emergency-${shift.id}`}>
      <Siren className="size-4 text-rose-700" /><span className="text-sm font-medium text-rose-900">{title}</span>
      <span className="ml-auto text-xs text-rose-800">{t("cancel.needed")}</span>
      <Input type="number" min={1} value={needed} onChange={(e) => setNeeded(Number(e.target.value))} className="h-8 w-16 bg-white" data-testid={`emergency-needed-${shift.id}`} />
      <Button size="sm" variant="destructive" disabled={m.isPending} onClick={() => m.mutate()} data-testid={`emergency-send-${shift.id}`}>{t("cancel.sendUrgent")}</Button>
    </div>
  );
}

export default function SmartCancellation() {
  const { t } = useTranslation();
  const [target, setTarget] = useState<Target | null>(null);
  const q = useQuery({ queryKey: ["ngo-cancellations"], queryFn: () => apiGet<CancellationOverview>("/ngo/cancellations") });
  return (
    <div>
      <PageHeader title={t("cancel.title")} sub={t("cancel.sub")} />
      <div className="grid gap-6 xl:grid-cols-12">
        <div className="space-y-6 xl:col-span-5">
          <Panel title={t("cancel.vacancies")} testId="vacancies-panel">
            {q.isLoading ? <Loading /> : !q.data?.vacancies.length ? <Empty text={t("cancel.noVacancies")} /> : (
              <ul className="space-y-3">{q.data.vacancies.map((v) => {
                const active = target?.regId === v.cancelled_registration_id;
                return (
                  <li key={v.cancelled_registration_id} data-testid={`vacancy-${v.cancelled_registration_id}`}
                    className={cn("rounded-xl border p-4 transition-colors", active ? "border-sky-400 bg-sky-50/60" : v.replaced_by_name ? "border-emerald-200 bg-emerald-50/50" : "border-rose-200 bg-rose-50/50")}>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold text-slate-900">{v.event_title}</p>
                        <p className="text-xs text-slate-600">{fmtDate(v.shift.shift_date)} · {fmtTime(v.shift.start_time)}–{fmtTime(v.shift.end_time)}</p>
                        <p className="mt-1 inline-flex items-center gap-1 text-sm text-rose-800"><UserMinus className="size-4" />{t("cancel.cancelledBy", { name: v.cancelled_volunteer_name })}
                          {v.last_minute && <span className="ml-1 rounded bg-rose-600 px-1.5 text-[10px] font-bold uppercase text-white">{t("cancel.lastMinute")}</span>}</p>
                      </div>
                      {v.replaced_by_name ? <StatusBadge status="filled" testId={`vacancy-filled-${v.cancelled_registration_id}`} /> : <StatusBadge status={v.shift.coverage.status} />}
                    </div>
                    {v.replaced_by_name ? <p className="mt-2 text-sm font-medium text-emerald-800" data-testid={`vacancy-replaced-${v.cancelled_registration_id}`}>{t("cancel.replacedBy", { name: v.replaced_by_name })}</p> : (
                      <Button size="sm" className="mt-3" onClick={() => setTarget({ shiftId: v.shift.id, regId: v.cancelled_registration_id, title: v.event_title })} data-testid={`find-replacements-${v.cancelled_registration_id}`}>
                        <Sparkles />{t("cancel.findReplacements")}{v.invitations_sent > 0 && ` · ${v.invitations_sent} ${t("cancel.invited").toLowerCase()}`}</Button>
                    )}
                  </li>);
              })}</ul>)}
          </Panel>
          <Panel title={t("cancel.emergencyMode")} testId="emergency-panel">
            <p className="mb-3 text-sm text-slate-600">{t("cancel.emergencyDesc")}</p>
            {!q.data?.understaffed.length ? <Empty /> : (
              <div className="space-y-3">{q.data.understaffed.slice(0, 8).map((a) => (
                <div key={a.shift.id} className="space-y-2 rounded-xl border border-slate-200 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-slate-900">{a.event_title} · {fmtDate(a.shift.shift_date)} {fmtTime(a.shift.start_time)}</p>
                    <Button size="xs" variant="outline" onClick={() => setTarget({ shiftId: a.shift.id, regId: null, title: a.event_title })} data-testid={`shift-candidates-${a.shift.id}`}><Search />{t("cancel.candidates")}</Button>
                  </div>
                  <CoverageBar c={a.shift.coverage} />
                  {a.shift.coverage.status === "critical_shortage" && <Emergency shift={a.shift} title={t("cancel.emergencyMode")} />}
                </div>))}
              </div>)}
          </Panel>
        </div>
        <div className="xl:col-span-7">
          <Panel title={target ? `${t("cancel.candidates")} — ${target.title}` : t("cancel.candidates")}>
            {target ? <Candidates key={`${target.shiftId}-${target.regId}`} target={target} /> : <Empty text={t("cancel.findReplacements")} testId="candidates-placeholder" />}
          </Panel>
        </div>
      </div>
    </div>
  );
}
