import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Bell, BellRing, CheckCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Empty, Loading, PageHeader } from "@/components/shared";
import { apiGet, apiPost } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { useMe } from "@/lib/session";
import type { Notification } from "@/lib/types";
import { cn } from "@/lib/utils";

export function useNotifText() {
  const { t } = useTranslation();
  return (n: Notification) => ({
    title: t(`notif.types.${n.notification_type}.t`, { ...n.params, defaultValue: n.title }),
    message: t(`notif.types.${n.notification_type}.m`, { ...n.params, defaultValue: n.message }),
  });
}

export function NotificationItem({ n, onRead }: { n: Notification; onRead?: () => void }) {
  const { t } = useTranslation();
  const text = useNotifText()(n);
  const urgent = ["urgent_request", "volunteer_cancelled", "reminder_2h", "invite_expired_none"].includes(n.notification_type);
  return (
    <li data-testid={`notification-${n.id}`} className={cn("flex gap-3 rounded-xl border p-4 transition-colors",
      n.read_status ? "border-slate-200 bg-white" : urgent ? "border-rose-200 bg-rose-50/60" : "border-sky-200 bg-sky-50/60")}>
      <div className={cn("grid size-9 shrink-0 place-items-center rounded-full", urgent ? "bg-rose-100 text-rose-700" : "bg-sky-100 text-sky-700")}>
        {urgent ? <BellRing className="size-4" /> : <Bell className="size-4" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-slate-900">{text.title}</p>
        <p className="text-sm text-slate-700">{text.message}</p>
        <p className="mt-1 text-xs text-slate-500">{fmtDateTime(n.created_at)}</p>
      </div>
      {!n.read_status && onRead && <Button size="xs" variant="outline" onClick={onRead} data-testid={`notification-read-${n.id}`}>{t("notif.markRead")}</Button>}
    </li>
  );
}

export default function Notifications() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const q = useQuery({ queryKey: ["notifications"], queryFn: () => apiGet<Notification[]>("/notifications") });
  const done = () => { qc.invalidateQueries({ queryKey: ["notifications"] }); qc.invalidateQueries({ queryKey: ["vdash"] }); };
  const readOne = useMutation({ mutationFn: (id: string) => apiPost(`/notifications/${id}/read`), onSuccess: done });
  const readAll = useMutation({ mutationFn: () => apiPost("/notifications/read-all"), onSuccess: done });
  const link = (n: Notification) => !n.related_event_id ? null
    : me?.role === "ngo" ? (["volunteer_cancelled", "invite_forwarded", "invite_expired_none", "replacement_declined"].includes(n.notification_type) ? "/ngo/cancellations" : `/ngo/events/${n.related_event_id}`)
    : ["replacement_invitation", "urgent_request"].includes(n.notification_type) ? "/volunteer/invitations" : `/volunteer/events/${n.related_event_id}`;
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title={t("nav.notifications")} sub={t("notif.inAppOnly")}
        actions={<Button variant="outline" onClick={() => readAll.mutate()} data-testid="notifications-mark-all"><CheckCheck />{t("notif.markAll")}</Button>} />
      {q.isLoading ? <Loading /> : q.isError || !q.data?.length ? <Empty text={t("notif.empty")} /> : (
        <ul className="space-y-3">
          {q.data.map((n) => {
            const to = link(n);
            return to
              ? <Link key={n.id} to={to} onClick={() => !n.read_status && readOne.mutate(n.id)} className="block"><NotificationItem n={n} /></Link>
              : <NotificationItem key={n.id} n={n} onRead={() => readOne.mutate(n.id)} />;
          })}
        </ul>
      )}
    </div>
  );
}
