import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { CalendarDays, Clock, ImagePlus, Loader2, MapPin, Siren, Users } from "lucide-react";
import { toast } from "sonner";
import { apiUpload } from "@/lib/api";
import { errMsg, fmtDate, fmtTime, initials, localized } from "@/lib/format";
import type { Coverage, EventCard, UploadOut } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<string, string> = {
  fully_staffed: "bg-green-100 text-green-800 border-green-300",
  partially_staffed: "bg-amber-100 text-amber-800 border-amber-200",
  critical_shortage: "bg-red-100 text-red-800 border-red-300",
  fully_booked: "bg-indigo-100 text-indigo-800 border-indigo-200",
  published: "bg-sky-100 text-sky-800 border-sky-200", draft: "bg-slate-100 text-slate-700 border-slate-300",
  unpublished: "bg-slate-100 text-slate-600 border-slate-300", confirmed: "bg-sky-100 text-sky-800 border-sky-200",
  cancelled: "bg-red-50 text-red-700 border-red-200", completed: "bg-green-100 text-green-800 border-green-300",
  absent: "bg-slate-100 text-slate-600 border-slate-300", pending: "bg-amber-100 text-amber-800 border-amber-200",
  accepted: "bg-green-100 text-green-800 border-green-300", declined: "bg-slate-100 text-slate-600 border-slate-300",
  expired: "bg-slate-100 text-slate-500 border-slate-200", filled: "bg-slate-100 text-slate-600 border-slate-300",
  emergency: "bg-rose-100 text-rose-800 border-rose-300", replacement: "bg-teal-100 text-teal-800 border-teal-200",
  verified: "bg-green-100 text-green-800 border-green-300",
};

export function StatusBadge({ status, testId }: { status: string; testId?: string }) {
  const { t } = useTranslation();
  return (
    <span data-testid={testId ?? `status-badge-${status}`}
      className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        STATUS_STYLE[status] ?? "bg-slate-100 text-slate-700 border-slate-200")}>
      {t(`status.${status}`, { defaultValue: status })}
    </span>
  );
}

export function DemoBadge({ show }: { show: boolean }) {
  const { t } = useTranslation();
  if (!show) return null;
  return <span data-testid="demo-badge" className="rounded-md bg-violet-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700 ring-1 ring-violet-200">{t("common.demo")}</span>;
}

export function StatCard({ label, value, icon, tone = "sky", testId }: { label: string; value: ReactNode; icon: ReactNode; tone?: "sky" | "green" | "amber" | "red" | "teal"; testId: string }) {
  const tones = { sky: "bg-sky-50 text-sky-700", green: "bg-emerald-50 text-emerald-700", amber: "bg-amber-50 text-amber-700", red: "bg-red-50 text-red-700", teal: "bg-teal-50 text-teal-700" };
  return (
    <div data-testid={testId} className="vc-rise flex items-center justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow duration-200 hover:shadow-md">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
        <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900" data-testid={`${testId}-value`}>{value}</p>
      </div>
      <div className={cn("grid size-11 place-items-center rounded-xl", tones[tone])}>{icon}</div>
    </div>
  );
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl" data-testid="page-title">{title}</h1>
        {sub && <p className="mt-1 max-w-3xl text-sm text-slate-600">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ title, children, action, className, testId }: { title?: string; children: ReactNode; action?: ReactNode; className?: string; testId?: string }) {
  return (
    <section data-testid={testId} className={cn("rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm sm:p-6", className)}>
      {title && <div className="mb-4 flex items-center justify-between gap-2"><h2 className="text-lg font-semibold text-slate-900">{title}</h2>{action}</div>}
      {children}
    </section>
  );
}

export function Empty({ text, testId = "empty-state" }: { text?: string; testId?: string }) {
  const { t } = useTranslation();
  return <div data-testid={testId} className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">{text ?? t("common.empty")}</div>;
}

export function Loading() {
  const { t } = useTranslation();
  return <div className="flex items-center gap-2 py-8 text-sm text-slate-500" data-testid="loading"><Loader2 className="size-4 animate-spin" />{t("common.loading")}</div>;
}

export function Avatar({ src, name, size = 40 }: { src?: string; name: string; size?: number }) {
  const [broken, setBroken] = useState(false);
  return src && !broken
    ? <img src={src} alt={name} onError={() => setBroken(true)} style={{ width: size, height: size }} className="rounded-full object-cover ring-2 ring-white" />
    : <div style={{ width: size, height: size }} className="grid place-items-center rounded-full bg-sky-100 text-sm font-bold text-sky-800">{initials(name)}</div>;
}

export function ChipSelect({ options, value, onChange, ns, testId }: { options: string[]; value: string[]; onChange: (v: string[]) => void; ns: string; testId: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap gap-2" data-testid={testId}>
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <button type="button" key={o} data-testid={`${testId}-${o}`} aria-pressed={on}
            onClick={() => onChange(on ? value.filter((x) => x !== o) : [...value, o])}
            className={cn("rounded-full border px-3 py-1 text-sm font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-sky-500",
              on ? "border-sky-600 bg-sky-600 text-white" : "border-slate-300 bg-white text-slate-700 hover:border-sky-400 hover:bg-sky-50")}>
            {t(`${ns}.${o}`, { defaultValue: o })}
          </button>
        );
      })}
    </div>
  );
}

export function SkillChips({ skills, highlight = [] }: { skills: string[]; highlight?: string[] }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap gap-1.5">
      {skills.map((s) => (
        <span key={s} className={cn("rounded-md px-2 py-0.5 text-xs font-medium",
          highlight.includes(s) ? "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-300" : "bg-slate-100 text-slate-700")}>
          {t(`skills.${s}`, { defaultValue: s })}
        </span>
      ))}
    </div>
  );
}

export function CoverageBar({ c, testId }: { c: Coverage; testId?: string }) {
  const { t } = useTranslation();
  const color = { fully_staffed: "bg-emerald-500", partially_staffed: "bg-amber-500", critical_shortage: "bg-red-500", fully_booked: "bg-indigo-500" }[c.status];
  return (
    <div data-testid={testId} className="space-y-1.5">
      <div className="flex items-center justify-between text-xs text-slate-600">
        <span>{c.registered}/{c.required} · {c.coverage_pct}%</span><StatusBadge status={c.status} />
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className={cn("h-full rounded-full transition-[width] duration-500", color)} style={{ width: `${Math.min(100, c.coverage_pct)}%` }} /></div>
      {c.missing_skills.length > 0 && (
        <p className="text-xs text-red-700">{t("shift.missing")}: {c.missing_skills.map((g) => `${t(`skills.${g.skill}`, { defaultValue: g.skill })} (${g.have}/${g.required})`).join(", ")}</p>
      )}
    </div>
  );
}

export function EventCardView({ ev, to }: { ev: EventCard; to: string }) {
  const { t } = useTranslation();
  const { title } = localized(ev);
  const left = Math.max(0, ev.total_capacity - ev.total_filled);
  return (
    <Link to={to} data-testid={`event-card-${ev.id}`} className="group vc-rise flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-md">
      <div className="relative h-36 bg-slate-100">
        {ev.image_url && <img src={ev.image_url} alt="" className="h-full w-full object-cover" />}
        <div className="absolute left-3 top-3 flex gap-1.5">
          {ev.emergency && <span className="vc-pulse inline-flex items-center gap-1 rounded-full bg-rose-600 px-2 py-0.5 text-xs font-semibold text-white"><Siren className="size-3" />{t("status.emergency")}</span>}
          <span className="rounded-full bg-white/90 px-2 py-0.5 text-xs font-medium text-slate-800">{t(`categories.${ev.category}`, { defaultValue: ev.category })}</span>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold leading-snug text-slate-900 group-hover:text-sky-700">{title}</h3>
          <DemoBadge show={ev.is_demo} />
        </div>
        <p className="text-sm text-slate-600">{ev.ngo_name}</p>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1"><CalendarDays className="size-3.5" />{fmtDate(ev.event_date)}</span>
          <span className="inline-flex items-center gap-1"><Clock className="size-3.5" />{fmtTime(ev.start_time)}–{fmtTime(ev.end_time)}</span>
          <span className="inline-flex items-center gap-1"><MapPin className="size-3.5" />{ev.location}</span>
        </div>
        <div className="mt-auto flex items-center justify-between pt-2">
          <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-700"><Users className="size-3.5" />{t("event.spotsLeft", { count: left })}</span>
          <StatusBadge status={ev.status === "published" ? ev.coverage_status : ev.status} />
        </div>
      </div>
    </Link>
  );
}

export function ImageUpload({ value, onChange, testId, round }: { value: string; onChange: (url: string) => void; testId: string; round?: boolean }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  async function pick(f?: File) {
    if (!f) return;
    setBusy(true);
    try { onChange((await apiUpload<UploadOut>("/uploads", f)).url); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  }
  return (
    <div className="flex items-center gap-4">
      <div className={cn("grid size-20 shrink-0 place-items-center overflow-hidden bg-slate-100 ring-1 ring-slate-200", round ? "rounded-full" : "rounded-xl")}>
        {value ? <img src={value} alt="" className="h-full w-full object-cover" /> : <ImagePlus className="size-6 text-slate-400" />}
      </div>
      <label className="cursor-pointer rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50">
        {busy ? <Loader2 className="inline size-4 animate-spin" /> : t("common.upload")}
        <input data-testid={testId} type="file" accept="image/*" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
      </label>
    </div>
  );
}

export const Field = ({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) => (
  <label className="block space-y-1.5"><span className="text-sm font-medium text-slate-700">{label}</span>{children}{hint && <span className="block text-xs text-slate-500">{hint}</span>}</label>
);

export const selectCls = "h-9 w-full rounded-lg border border-input bg-white px-3 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500";
