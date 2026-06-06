import type { ReactNode } from "react";
import { useAdminLayout } from "../hooks/useAdminLayout";
import AdminSidebar from "../ui/AdminSidebar";
import AdminHeader from "../ui/AdminHeader";

interface AdminLayoutProps {
  children: ReactNode;
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  const { menus, activePath, displayName, role, handleLogout } =
    useAdminLayout();

  return (
    <div className="flex h-screen">
      <AdminSidebar menus={menus} activePath={activePath} />
      <div className="flex flex-col flex-1 min-w-0">
        <AdminHeader
          displayName={displayName}
          role={role}
          onLogout={handleLogout}
        />
        <main className="flex-1 bg-[#f5f7fa] p-5 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
