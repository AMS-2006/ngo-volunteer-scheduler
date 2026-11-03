import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ChipSelect, Field, selectCls } from "@/components/shared";
import { LocationPicker } from "@/components/MapView";
import { PublicNav } from "@/pages/Public";
import { apiPost } from "@/lib/api";
import { CATEGORIES, errMsg } from "@/lib/format";
import { LANGS, setLanguage } from "@/lib/i18n";
import { beginSession, homeFor, useMe } from "@/lib/session";
import type { Lang, MessageOut, RegisterIn, User } from "@/lib/types";

function AuthLayout({ title, children, wide }: { title: string; children: ReactNode; wide?: boolean }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="relative bg-slate-900 pb-24 pt-24"><PublicNav /></div>
      <div className={`mx-auto -mt-16 px-4 pb-16 ${wide ? "max-w-3xl" : "max-w-md"}`}>
        <div className="vc-rise rounded-2xl border border-slate-200 bg-white p-6 shadow-lg sm:p-8">
          <h1 className="mb-6 text-2xl font-bold tracking-tight text-slate-900" data-testid="page-title">{title}</h1>
          {children}
        </div>
      </div>
    </div>
  );
}

const DEMO = [
  { label: "NGO · Annapurna Food Trust", email: "annapurna@demo.vc" },
  { label: "NGO · Jeevan Health Foundation", email: "jeevan@demo.vc" },
  { label: "Volunteer · Priya Sharma", email: "priya@demo.vc" },
  { label: "Volunteer · Kavya Reddy (top replacement)", email: "kavya@demo.vc" },
];

export function Login() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const { data: me } = useMe();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const m = useMutation({
    mutationFn: () => apiPost<User>("/auth/login", { email, password }),
    onSuccess: (u) => { beginSession(u); nav(homeFor(u)); },
    onError: (e) => toast.error(errMsg(e)),
  });
  if (me) return <Navigate to={homeFor(me)} replace />;
  return (
    <AuthLayout title={t("auth.welcome")}>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label={t("auth.email")}><Input data-testid="login-email-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label={t("auth.password")}><Input data-testid="login-password-input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <Button type="submit" className="w-full" disabled={m.isPending} data-testid="login-submit-button">{m.isPending && <Loader2 className="animate-spin" />}{t("auth.signIn")}</Button>
        <div className="flex justify-between text-sm">
          <Link to="/forgot-password" className="text-sky-700 hover:underline" data-testid="forgot-password-link">{t("auth.forgot")}</Link>
          <Link to="/register" className="text-sky-700 hover:underline" data-testid="login-register-link">{t("auth.signUp")}</Link>
        </div>
      </form>
      <div className="mt-6 rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{t("auth.demoAccounts")}</p>
        <div className="grid gap-1.5">
          {DEMO.map((d) => (
            <button key={d.email} type="button" data-testid={`demo-login-${d.email.split("@")[0]}`}
              onClick={() => { setEmail(d.email); setPassword("Demo@1234"); }}
              className="rounded-lg px-2 py-1.5 text-left text-sm text-slate-700 transition-colors hover:bg-white hover:text-sky-700">{d.label} <span className="text-slate-400">— {d.email}</span></button>
          ))}
        </div>
      </div>
    </AuthLayout>
  );
}

export function Register() {
  const { role = "volunteer" } = useParams();
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const isNgo = role === "ngo";
  const [f, setF] = useState<RegisterIn>({
    role: isNgo ? "ngo" : "volunteer", full_name: "", email: "", password: "", phone: "", location: "", latitude: null,
    longitude: null, preferred_language: (i18n.language as Lang) ?? "en", description: "", causes: [],
  });
  const set = <K extends keyof RegisterIn>(k: K, v: RegisterIn[K]) => setF((p) => ({ ...p, [k]: v }));
  const m = useMutation({
    mutationFn: () => apiPost<User>("/auth/register", { ...f, role: isNgo ? "ngo" : "volunteer" }),
    onSuccess: (u) => { beginSession(u); toast.success(t("common.saved")); nav(isNgo ? "/ngo/profile" : "/volunteer/profile"); },
    onError: (e) => toast.error(errMsg(e)),
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (isNgo && f.causes.length === 0) return toast.error(t("auth.causes"));
    m.mutate();
  }
  if (role !== "ngo" && role !== "volunteer") return <Navigate to="/register" replace />;
  return (
    <AuthLayout title={isNgo ? t("auth.ngoSignup") : t("auth.volSignup")} wide>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={submit}>
        <Field label={isNgo ? t("auth.orgName") : t("auth.fullName")}><Input data-testid="register-name-input" required minLength={2} value={f.full_name} onChange={(e) => set("full_name", e.target.value)} /></Field>
        <Field label={isNgo ? t("auth.officialEmail") : t("auth.email")}><Input data-testid="register-email-input" type="email" required value={f.email} onChange={(e) => set("email", e.target.value)} /></Field>
        <Field label={t("auth.password")} hint={t("auth.minPw")}><Input data-testid="register-password-input" type="password" required minLength={8} value={f.password} onChange={(e) => set("password", e.target.value)} /></Field>
        <Field label={t("auth.phone")}><Input data-testid="register-phone-input" required minLength={6} value={f.phone} onChange={(e) => set("phone", e.target.value)} /></Field>
        <div className="sm:col-span-2"><Field label={t("auth.location")}>
          <LocationPicker testId="register-location" location={f.location} lat={f.latitude} lng={f.longitude}
            onChange={(v) => setF((p) => ({ ...p, ...v }))} />
        </Field></div>
        {isNgo ? (
          <>
            <div className="sm:col-span-2"><Field label={t("auth.description")}><Textarea data-testid="register-description-input" required minLength={10} value={f.description} onChange={(e) => set("description", e.target.value)} /></Field></div>
            <div className="sm:col-span-2"><Field label={t("auth.causes")}><ChipSelect testId="register-causes" ns="categories" options={CATEGORIES} value={f.causes} onChange={(v) => set("causes", v)} /></Field></div>
          </>
        ) : (
          <Field label={t("auth.language")}>
            <select data-testid="register-language-select" className={selectCls} value={f.preferred_language}
              onChange={(e) => { set("preferred_language", e.target.value as Lang); setLanguage(e.target.value, false); }}>
              {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
          </Field>
        )}
        <div className="sm:col-span-2">
          <Button type="submit" className="w-full" disabled={m.isPending} data-testid="register-submit-button">{m.isPending && <Loader2 className="animate-spin" />}{t("auth.signUp")}</Button>
          <p className="mt-3 text-center text-sm text-slate-600">{t("auth.haveAccount")} <Link to="/login" className="font-semibold text-sky-700" data-testid="register-login-link">{t("nav.login")}</Link></p>
        </div>
      </form>
    </AuthLayout>
  );
}

export function ForgotPassword() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const m = useMutation({ mutationFn: () => apiPost<MessageOut>("/auth/forgot-password", { email }), onSuccess: (r) => setMsg(r.message), onError: (e) => toast.error(errMsg(e)) });
  return (
    <AuthLayout title={t("auth.resetTitle")}>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label={t("auth.email")}><Input data-testid="forgot-email-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Button type="submit" className="w-full" disabled={m.isPending} data-testid="forgot-submit-button">{m.isPending && <Loader2 className="animate-spin" />}{t("auth.sendReset")}</Button>
        {msg && <p data-testid="forgot-result-message" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800 ring-1 ring-emerald-200">{msg}</p>}
        <Link to="/login" className="block text-center text-sm text-sky-700" data-testid="forgot-back-login">{t("nav.login")}</Link>
      </form>
    </AuthLayout>
  );
}

export function ResetPassword() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [password, setPassword] = useState("");
  const m = useMutation({
    mutationFn: () => apiPost<MessageOut>("/auth/reset-password", { token: params.get("token") ?? "", password }),
    onSuccess: (r) => { toast.success(r.message); nav("/login"); }, onError: (e) => toast.error(errMsg(e)),
  });
  return (
    <AuthLayout title={t("auth.resetTitle")}>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <Field label={t("auth.newPassword")} hint={t("auth.minPw")}><Input data-testid="reset-password-input" type="password" minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <Button type="submit" className="w-full" disabled={m.isPending} data-testid="reset-submit-button">{t("common.save")}</Button>
      </form>
    </AuthLayout>
  );
}
