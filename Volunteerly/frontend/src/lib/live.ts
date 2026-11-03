import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiGet } from "@/lib/api";
import type { LiveOut, Notification } from "@/lib/types";
import { useNotifText } from "@/pages/Notifications";

const POLL_MS = 3000;

/** Polls the server's change counter; when anything changes (a registration, cancellation, acceptance…)
 *  every open view refetches, so dashboards and coverage bars update without a reload. */
export function useLiveSync(enabled: boolean) {
  const qc = useQueryClient();
  const last = useRef<number | null>(null);
  const q = useQuery({
    queryKey: ["live"], queryFn: () => apiGet<LiveOut>("/live"), enabled,
    refetchInterval: POLL_MS, refetchIntervalInBackground: false, staleTime: 0,
  });
  useEffect(() => {
    const v = q.data?.version;
    if (v == null) return;
    if (last.current != null && v !== last.current) {
      qc.invalidateQueries({ predicate: (x) => !["live", "me"].includes(String(x.queryKey[0])) });
    }
    last.current = v;
  }, [q.data?.version, qc]);
  return { connected: q.isSuccess && !q.isError };
}

/** Pops a toast for notifications that arrive while the user is on any page. */
export function useNewNotificationToasts(notes: Notification[] | undefined) {
  const seen = useRef<Set<string> | null>(null);
  const text = useNotifText();
  useEffect(() => {
    if (!notes) return;
    if (seen.current == null) { seen.current = new Set(notes.map((n) => n.id)); return; }
    for (const n of notes) {
      if (seen.current.has(n.id)) continue;
      seen.current.add(n.id);
      if (!n.read_status) { const m = text(n); toast.info(m.title, { description: m.message }); }
    }
  }, [notes, text]);
}
