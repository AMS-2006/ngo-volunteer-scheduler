import { useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";
import { setLanguage } from "@/lib/i18n";
import type { User } from "@/lib/types";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => apiGet<User | null>("/auth/session"), retry: false, staleTime: 60_000 });
}

export function beginSession(user: User) {
  queryClient.clear();
  queryClient.setQueryData(["me"], user);
  setLanguage(user.preferred_language, false);
}

export async function endSession() {
  await apiPost("/auth/logout").catch(() => undefined);
  queryClient.clear();
  queryClient.setQueryData(["me"], null);
}

export const homeFor = (u: User) => (u.role === "ngo" ? "/ngo/dashboard" : "/volunteer/dashboard");
