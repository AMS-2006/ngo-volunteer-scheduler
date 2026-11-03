import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import AppShell from "@/components/AppShell";
import { About, Landing, RoleSelect } from "@/pages/Public";
import { ForgotPassword, Login, Register, ResetPassword } from "@/pages/Auth";
import Notifications from "@/pages/Notifications";
import { NgoAnalyticsPage, NgoCoverage, NgoDashboard, NgoEvents, NgoProfile, NgoRegistrations, NgoVolunteers } from "@/pages/NgoPages";
import NgoEventForm from "@/pages/NgoEventForm";
import NgoEventManage from "@/pages/NgoEventManage";
import SmartCancellation from "@/pages/SmartCancellation";
import { Discover, EventDetails, History, Invitations, MyRegistrations, NgoPublicPage, VolDashboard, VolProfile } from "@/pages/VolunteerPages";

// One <Route> per page in src/pages; BrowserRouter already wraps this in main.tsx.
export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/about" element={<About />} />
        <Route path="/register" element={<RoleSelect />} />
        <Route path="/register/:role" element={<Register />} />
        <Route path="/login" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/ngo" element={<AppShell role="ngo" />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<NgoDashboard />} />
          <Route path="profile" element={<NgoProfile />} />
          <Route path="events" element={<NgoEvents />} />
          <Route path="events/new" element={<NgoEventForm />} />
          <Route path="events/:id" element={<NgoEventManage />} />
          <Route path="events/:id/edit" element={<NgoEventForm />} />
          <Route path="registrations" element={<NgoRegistrations />} />
          <Route path="coverage" element={<NgoCoverage />} />
          <Route path="cancellations" element={<SmartCancellation />} />
          <Route path="volunteers" element={<NgoVolunteers />} />
          <Route path="analytics" element={<NgoAnalyticsPage />} />
          <Route path="notifications" element={<Notifications />} />
        </Route>
        <Route path="/volunteer" element={<AppShell role="volunteer" />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<VolDashboard />} />
          <Route path="profile" element={<VolProfile />} />
          <Route path="discover" element={<Discover />} />
          <Route path="events/:id" element={<EventDetails />} />
          <Route path="ngos/:id" element={<NgoPublicPage />} />
          <Route path="registrations" element={<MyRegistrations />} />
          <Route path="invitations" element={<Invitations />} />
          <Route path="history" element={<History />} />
          <Route path="notifications" element={<Notifications />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster richColors position="bottom-right" />
    </>
  );
}
