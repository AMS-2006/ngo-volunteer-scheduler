import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, Building2, Globe2, HandHeart, ShieldCheck, Sparkles, UserRound, Workflow } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { LanguageSwitcher } from "@/components/AppShell";
import { cn } from "@/lib/utils";

const HERO = "https://images.unsplash.com/photo-1542323228-002ac256e7b8?crop=entropy&cs=srgb&fm=jpg&q=80&w=1600";

export function PublicNav() {
  const { t } = useTranslation();
  return (
    <header className="absolute inset-x-0 top-0 z-20">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-4 sm:px-8">
        <Link to="/" className="flex items-center gap-2 text-white" data-testid="public-brand-link">
          <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-sky-500 to-emerald-500"><HandHeart className="size-5" /></span>
          <span className="text-lg font-bold">{t("brand")}</span>
        </Link>
        <nav className="ml-auto flex items-center gap-2 sm:gap-4">
          <Link to="/about" className="hidden text-sm font-medium text-slate-200 hover:text-white sm:block" data-testid="nav-about">{t("nav.about")}</Link>
          <Link to="/login" className="text-sm font-medium text-slate-200 hover:text-white" data-testid="nav-login">{t("nav.login")}</Link>
          <LanguageSwitcher dark />
          <Link to="/register" className={cn(buttonVariants({ size: "sm" }), "bg-sky-500 hover:bg-sky-400")} data-testid="nav-register">{t("nav.register")}</Link>
        </nav>
      </div>
    </header>
  );
}

export function Landing() {
  const { t } = useTranslation();
  const features = [
    { icon: Sparkles, title: t("landing.f1"), d: t("landing.f1d") },
    { icon: ShieldCheck, title: t("landing.f2"), d: t("landing.f2d") },
    { icon: Globe2, title: t("landing.f3"), d: t("landing.f3d") },
  ];
  const steps = [t("landing.h1"), t("landing.h2"), t("landing.h3"), t("landing.h4")];
  return (
    <div className="min-h-screen bg-slate-50">
      <section className="relative overflow-hidden bg-slate-900">
        <img src={HERO} alt="" className="absolute inset-0 h-full w-full object-cover opacity-40" />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950/95 via-slate-900/85 to-sky-950/70" />
        <PublicNav />
        <div className="relative mx-auto grid max-w-7xl gap-10 px-4 pb-20 pt-32 sm:px-8 lg:grid-cols-12 lg:pt-40">
          <div className="vc-rise lg:col-span-7">
            <span className="inline-flex items-center gap-2 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-300 ring-1 ring-emerald-400/30">{t("landing.tagline")}</span>
            <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight text-white sm:text-5xl" data-testid="landing-hero-title">{t("landing.heroTitle")}</h1>
            <p className="mt-5 max-w-2xl text-lg text-slate-300">{t("landing.heroSub")}</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link to="/register/ngo" data-testid="landing-register-ngo" className={cn(buttonVariants({ size: "lg" }), "h-12 bg-sky-500 px-6 text-base hover:bg-sky-400")}><Building2 className="size-5" />{t("landing.ctaNgo")}</Link>
              <Link to="/register/volunteer" data-testid="landing-register-volunteer" className={cn(buttonVariants({ size: "lg", variant: "outline" }), "h-12 border-white/30 bg-white/10 px-6 text-base text-white hover:bg-white/20")}><UserRound className="size-5" />{t("landing.ctaVol")}</Link>
            </div>
          </div>
          <div className="lg:col-span-5">
            <div className="rounded-2xl border border-white/10 bg-white/10 p-6 backdrop-blur-md">
              <p className="flex items-center gap-2 text-sm font-semibold text-white"><Workflow className="size-4 text-emerald-300" />{t("landing.howTitle")}</p>
              <ol className="mt-4 space-y-3">
                {steps.map((s, i) => (
                  <li key={s} className="vc-rise flex items-center gap-3 rounded-xl bg-slate-900/60 p-3 text-sm text-slate-100" style={{ animationDelay: `${i * 90}ms` }}>
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-sky-500 text-xs font-bold text-white">{i + 1}</span>{s}
                  </li>
                ))}
              </ol>
              <div className="mt-4 rounded-xl bg-emerald-500/10 p-3 text-xs text-emerald-200 ring-1 ring-emerald-400/20">40% skills · 30% availability · 20% distance · 10% interests</div>
            </div>
          </div>
        </div>
      </section>
      <section className="mx-auto grid max-w-7xl gap-5 px-4 py-16 sm:px-8 md:grid-cols-3">
        {features.map(({ icon: Icon, title, d }) => (
          <div key={title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-md">
            <div className="grid size-11 place-items-center rounded-xl bg-sky-50 text-sky-700"><Icon className="size-5" /></div>
            <h3 className="mt-4 text-lg font-semibold text-slate-900">{title}</h3>
            <p className="mt-1 text-sm text-slate-600">{d}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

export function About() {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="relative bg-slate-900 pb-16 pt-28"><PublicNav />
        <div className="mx-auto max-w-4xl px-4 sm:px-8"><h1 className="text-4xl font-bold text-white" data-testid="page-title">{t("about.title")}</h1></div>
      </div>
      <div className="mx-auto max-w-4xl space-y-5 px-4 py-12 text-slate-700 sm:px-8">
        <p className="text-lg">{t("about.body")}</p>
        <p className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-900">{t("about.privacy")}</p>
        <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900">{t("about.limits")}</p>
        <Link to="/register" className={buttonVariants()} data-testid="about-get-started">{t("nav.register")} <ArrowRight className="size-4" /></Link>
      </div>
    </div>
  );
}

export function RoleSelect() {
  const { t } = useTranslation();
  const roles = [
    { to: "/register/ngo", icon: Building2, title: t("auth.ngoRole"), d: t("auth.ngoRoleDesc"), id: "role-ngo-btn" },
    { to: "/register/volunteer", icon: UserRound, title: t("auth.volRole"), d: t("auth.volRoleDesc"), id: "role-volunteer-btn" },
  ];
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="relative bg-slate-900 pb-16 pt-28"><PublicNav />
        <div className="mx-auto max-w-4xl px-4 sm:px-8"><h1 className="text-3xl font-bold text-white sm:text-4xl" data-testid="page-title">{t("auth.chooseRole")}</h1></div>
      </div>
      <div className="mx-auto -mt-8 grid max-w-4xl gap-5 px-4 sm:grid-cols-2 sm:px-8">
        {roles.map(({ to, icon: Icon, title, d, id }) => (
          <Link key={to} to={to} data-testid={id} className="group rounded-2xl border border-slate-200 bg-white p-7 shadow-sm transition-[box-shadow,transform,border-color] duration-200 hover:-translate-y-1 hover:border-sky-300 hover:shadow-lg">
            <div className="grid size-12 place-items-center rounded-xl bg-gradient-to-br from-sky-500 to-emerald-500 text-white"><Icon className="size-6" /></div>
            <h2 className="mt-5 text-xl font-semibold text-slate-900">{title}</h2>
            <p className="mt-1 text-sm text-slate-600">{d}</p>
            <span className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-sky-700">{t("nav.register")} <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" /></span>
          </Link>
        ))}
      </div>
      <p className="py-8 text-center text-sm text-slate-600">{t("auth.haveAccount")} <Link className="font-semibold text-sky-700" to="/login" data-testid="role-login-link">{t("nav.login")}</Link></p>
    </div>
  );
}
