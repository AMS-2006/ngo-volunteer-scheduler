import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Eye, EyeOff, Pencil, Plus, Trash2, X } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { CoverageBar, Empty, Field, Loading, PageHeader, Panel, StatusBadge, selectCls } from "@/components/shared";
import { MapView } from "@/components/MapView";
import { RegistrationsTable } from "@/pages/NgoPages";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import { SKILLS, durationH, errMsg, fmtDate, fmtTime } from "@/lib/format";
import type { EventDetail, RegistrationRow, ShiftIn, ShiftWithCoverage } from "@/lib/types";

function ShiftDialog({ eventId, date, shift, onClose }: { eventId: string; date: string; shift: ShiftWithCoverage | "new" | null; onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const init: ShiftIn = shift && shift !== "new"
    ? { shift_date: shift.shift_date, start_time: shift.start_time, end_time: shift.end_time, capacity: shift.capacity, required_skills: shift.required_skills }
    : { shift_date: date, start_time: "08:00", end_time: "11:00", capacity: 5, required_skills: [] };
  const [f, setF] = useState<ShiftIn>(init);
  const save = useMutation({
    mutationFn: () => (shift && shift !== "new" ? apiPut(`/ngo/shifts/${shift.id}`, f) : apiPost(`/ngo/events/${eventId}/shifts`, f)),
    onSuccess: () => { qc.invalidateQueries(); toast.success(t("common.saved")); onClose(); },
    onError: (e) => toast.error(errMsg(e)),
  });
  const set = (p: Partial<ShiftIn>) => setF((x) => ({ ...x, ...p }));
  return (
    <Dialog open={!!shift} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="shift-dialog" className="sm:max-w-lg">
        <DialogHeader><DialogTitle>{shift === "new" ? t("shift.add") : t("shift.edit")}</DialogTitle></DialogHeader>
        <form className="grid grid-cols-2 gap-3" onSubmit={(e) => { e.preventDefault(); if (f.end_time <= f.start_time) return toast.error(t("event.end")); save.mutate(); }}>
          <div className="col-span-2"><Field label={t("common.date")}><Input data-testid="shift-date-input" type="date" required value={f.shift_date} onChange={(e) => set({ shift_date: e.target.value })} /></Field></div>
          <Field label={t("event.start")}><Input data-testid="shift-start-input" type="time" required value={f.start_time} onChange={(e) => set({ start_time: e.target.value })} /></Field>
          <Field label={t("event.end")} hint={`${durationH(f.start_time, f.end_time)} ${t("common.hours")}`}><Input data-testid="shift-end-input" type="time" required value={f.end_time} onChange={(e) => set({ end_time: e.target.value })} /></Field>
          <div className="col-span-2"><Field label={t("common.capacity")}><Input data-testid="shift-capacity-input" type="number" min={1} required value={f.capacity} onChange={(e) => set({ capacity: Number(e.target.value) })} /></Field></div>
          <div className="col-span-2 space-y-2">
            <p className="text-sm font-medium text-slate-700">{t("shift.skillReqs")}</p>
            {f.required_skills.map((r, i) => (
              <div key={i} className="flex gap-2">
                <select className={selectCls} value={r.skill} data-testid={`shift-skill-select-${i}`} onChange={(e) => set({ required_skills: f.required_skills.map((x, j) => (j === i ? { ...x, skill: e.target.value } : x)) })}>
                  {SKILLS.map((s) => <option key={s} value={s}>{t(`skills.${s}`)}</option>)}
                </select>
                <Input className="w-20" type="number" min={1} value={r.count} data-testid={`shift-skill-count-${i}`} onChange={(e) => set({ required_skills: f.required_skills.map((x, j) => (j === i ? { ...x, count: Number(e.target.value) } : x)) })} />
                <Button type="button" size="icon" variant="ghost" onClick={() => set({ required_skills: f.required_skills.filter((_, j) => j !== i) })} data-testid={`shift-skill-remove-${i}`}><X /></Button>
              </div>
            ))}
            <Button type="button" size="sm" variant="outline" onClick={() => set({ required_skills: [...f.required_skills, { skill: "logistics", count: 1 }] })} data-testid="shift-add-skill"><Plus />{t("shift.addSkill")}</Button>
          </div>
          <div className="col-span-2"><Button type="submit" className="w-full" disabled={save.isPending} data-testid="shift-save-button">{t("common.save")}</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function NgoEventManage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [dlg, setDlg] = useState<ShiftWithCoverage | "new" | null>(null);
  const q = useQuery({ queryKey: ["ngo-event", id], queryFn: () => apiGet<EventDetail>(`/ngo/events/${id}`) });
  const regs = useQuery({ queryKey: ["ngo-regs", id], queryFn: () => apiGet<RegistrationRow[]>(`/ngo/registrations?event_id=${id}`) });
  const status = useMutation({
    mutationFn: (s: string) => apiPost(`/ngo/events/${id}/status`, { status: s }),
    onSuccess: () => { qc.invalidateQueries(); toast.success(t("common.saved")); }, onError: (e) => toast.error(errMsg(e)),
  });
  const del = useMutation({ mutationFn: () => apiDelete(`/ngo/events/${id}`), onSuccess: () => { qc.invalidateQueries(); nav("/ngo/events"); } });
  const delShift = useMutation({ mutationFn: (sid: string) => apiDelete(`/ngo/shifts/${sid}`), onSuccess: () => qc.invalidateQueries(), onError: (e) => toast.error(errMsg(e)) });
  const ev = q.data;
  if (!ev) return q.isError ? <Empty /> : <Loading />;
  return (
    <div>
      <PageHeader title={ev.title} sub={`${fmtDate(ev.event_date)} · ${fmtTime(ev.start_time)}–${fmtTime(ev.end_time)} · ${ev.location}`} actions={<>
        <StatusBadge status={ev.status} testId="event-status-badge" />
        {ev.status === "published"
          ? <Button variant="outline" onClick={() => status.mutate("unpublished")} data-testid="event-unpublish-button"><EyeOff />{t("common.unpublish")}</Button>
          : <Button onClick={() => status.mutate("published")} data-testid="event-publish-button"><Eye />{t("common.publish")}</Button>}
        <Link to={`/ngo/events/${id}/edit`} className={buttonVariants({ variant: "outline" })} data-testid="event-edit-button"><Pencil />{t("common.edit")}</Link>
        <Button variant="destructive" onClick={() => confirm(t("event.deleteConfirm")) && del.mutate()} data-testid="event-delete-button"><Trash2 />{t("common.delete")}</Button>
      </>} />
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <Panel title={t("shift.title")} testId="shift-management-panel" action={<Button size="sm" onClick={() => setDlg("new")} data-testid="add-shift-button"><Plus />{t("shift.add")}</Button>}>
            {!ev.shifts.length ? <Empty text={t("event.noShifts")} /> : (
              <div className="space-y-3">{ev.shifts.map((s, i) => (
                <div key={s.id} className="rounded-xl border border-slate-200 p-4" data-testid={`shift-row-${s.id}`}>
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold text-slate-900">{t("common.shift")} {i + 1} · {fmtDate(s.shift_date)} · {fmtTime(s.start_time)}–{fmtTime(s.end_time)}</p>
                    <div className="flex gap-1">
                      <Button size="icon-sm" variant="ghost" onClick={() => setDlg(s)} data-testid={`edit-shift-${s.id}`}><Pencil /></Button>
                      <Button size="icon-sm" variant="ghost" onClick={() => confirm(t("shift.deleteConfirm")) && delShift.mutate(s.id)} data-testid={`delete-shift-${s.id}`}><Trash2 className="text-red-600" /></Button>
                    </div>
                  </div>
                  <CoverageBar c={s.coverage} testId={`shift-coverage-${s.id}`} />
                  {s.required_skills.length > 0 && <p className="mt-2 text-xs text-slate-600">{t("shift.skillReqs")}: {s.required_skills.map((r) => `${t(`skills.${r.skill}`)} ×${r.count}`).join(", ")}</p>}
                </div>))}
              </div>)}
          </Panel>
          <Panel title={t("shift.registeredVols")} testId="event-registrations-panel">
            {regs.data ? <RegistrationsTable rows={regs.data} showEvent={false} /> : <Loading />}
          </Panel>
        </div>
        <div className="space-y-6 lg:col-span-4">
          <Panel title={t("event.details")}>
            {ev.image_url && <img src={ev.image_url} alt="" className="mb-3 h-40 w-full rounded-lg object-cover" />}
            <p className="text-sm text-slate-700">{ev.description}</p>
            <dl className="mt-3 space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">{t("event.deadline")}</dt><dd>{ev.registration_deadline.replace("T", " ")}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">{t("event.requiredVolunteers")}</dt><dd>{ev.required_volunteers}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">{t("common.filled")}</dt><dd data-testid="event-filled-stat">{ev.total_filled}/{ev.total_capacity}</dd></div>
            </dl>
          </Panel>
          {ev.latitude != null && ev.longitude != null && <MapView height={240} markers={[{ id: ev.id, lat: ev.latitude, lng: ev.longitude, label: ev.location, urgent: ev.emergency }]} />}
        </div>
      </div>
      {dlg && <ShiftDialog key={dlg === "new" ? "new" : dlg.id} eventId={id} date={ev.event_date} shift={dlg} onClose={() => setDlg(null)} />}
    </div>
  );
}
