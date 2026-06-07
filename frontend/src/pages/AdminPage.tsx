import { Outlet, useLocation } from "@tanstack/react-router";
import AdminLayout from "../components/AdminLayout";
import DashboardCard from "../components/DashboardCard";

export default function AdminPage() {
  const loc = useLocation();
  const isRoot = loc.pathname === "/admin";

  return (
    <AdminLayout>
      {isRoot ? <DashboardCard /> : <Outlet />}
    </AdminLayout>
  );
}
