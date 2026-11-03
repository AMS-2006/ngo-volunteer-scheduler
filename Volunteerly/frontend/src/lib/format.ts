import i18n from "i18next";
import { ApiError } from "@/lib/api";
import type { VEvent } from "@/lib/types";

export const SKILLS = ["teaching", "first_aid", "event_management", "photography", "communication", "fundraising",
  "logistics", "graphic_design", "data_entry", "technical_support"];
export const INTERESTS = ["education", "healthcare", "environment", "animal_welfare", "disaster_relief", "community_service"];
export const CATEGORIES = ["education", "healthcare", "environment", "animal_welfare", "food_distribution", "disaster_relief",
  "community_development", "other"];
export const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
export const SLOTS = ["morning", "afternoon", "evening"];

export const PLACES: { name: string; lat: number; lng: number }[] = [
  { name: "Koramangala, Bengaluru", lat: 12.9352, lng: 77.6245 },
  { name: "Indiranagar, Bengaluru", lat: 12.9719, lng: 77.6412 },
  { name: "Jayanagar, Bengaluru", lat: 12.925, lng: 77.5938 },
  { name: "Whitefield, Bengaluru", lat: 12.9698, lng: 77.75 },
  { name: "Malleshwaram, Bengaluru", lat: 13.0031, lng: 77.5643 },
  { name: "HSR Layout, Bengaluru", lat: 12.9116, lng: 77.6474 },
  { name: "BTM Layout, Bengaluru", lat: 12.9166, lng: 77.6101 },
  { name: "Hebbal, Bengaluru", lat: 13.0358, lng: 77.597 },
  { name: "Electronic City, Bengaluru", lat: 12.8452, lng: 77.6602 },
  { name: "Mysuru", lat: 12.2958, lng: 76.6394 },
  { name: "Chennai", lat: 13.0827, lng: 80.2707 },
  { name: "Hyderabad", lat: 17.385, lng: 78.4867 },
  { name: "Mumbai", lat: 19.076, lng: 72.8777 },
  { name: "New Delhi", lat: 28.6139, lng: 77.209 },
];

export function errMsg(e: unknown): string {
  if (e instanceof ApiError) {
    const d = (e.body as { detail?: unknown } | null)?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d[0]?.msg) return `${d[0].loc?.slice(-1)[0] ?? ""}: ${d[0].msg}`;
  }
  return i18n.t("common.error");
}

export function fmtTime(t: string): string {
  const [h, m] = t.split(":").map(Number);
  const d = new Date(2000, 0, 1, h, m);
  return d.toLocaleTimeString(i18n.language + "-IN", { hour: "numeric", minute: "2-digit" });
}

export function fmtDate(iso: string): string {
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString(i18n.language + "-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString(i18n.language + "-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

export function durationH(start: string, end: string): number {
  const toM = (t: string) => Number(t.split(":")[0]) * 60 + Number(t.split(":")[1]);
  return Math.max(0, Math.round(((toM(end) - toM(start)) / 60) * 10) / 10);
}

/** Event title/description in the current language when a translation exists; original otherwise. */
export function localized(ev: Pick<VEvent, "title" | "description" | "translations">) {
  const tr = ev.translations?.[i18n.language];
  return { title: tr?.title || ev.title, description: tr?.description || ev.description };
}

export const initials = (n: string) => n.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
