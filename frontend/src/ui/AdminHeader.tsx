interface AdminHeaderProps {
  displayName: string;
  role: string;
  onLogout: () => void;
}

export default function AdminHeader({
  displayName,
  role,
  onLogout,
}: AdminHeaderProps) {
  return (
    <header className="h-15 bg-white flex items-center justify-between px-5 shadow-sm shrink-0">
      <span className="text-base font-medium">教务管理员端</span>
      <div className="flex items-center gap-4">
        <span className="text-[#606266]">{displayName}</span>
        <span className="badge badge-success">{role}</span>
        <button className="btn btn-error btn-sm" onClick={onLogout}>
          退出
        </button>
      </div>
    </header>
  );
}
