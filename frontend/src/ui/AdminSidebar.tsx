interface MenuItem {
  path: string;
  label: string;
}

interface AdminSidebarProps {
  menus: MenuItem[];
  activePath: string;
}

export default function AdminSidebar({ menus, activePath }: AdminSidebarProps) {
  return (
    <aside className="w-50 h-screen bg-[#304156] flex flex-col shrink-0">
      <div className="h-15 leading-15 text-center text-white text-lg font-bold border-b border-[#1f2d3d]">
        教务管理系统
      </div>
      <nav className="flex-1 py-2">
        {menus.map((menu) => {
          const isActive = activePath === menu.path;
          return (
            <a
              key={menu.path}
              href={menu.path}
              className={`block px-5 py-3 text-sm transition-colors
                ${isActive ? "text-[#409EFF]" : "text-[#bfcbd9] hover:text-white"}`}
            >
              {menu.label}
            </a>
          );
        })}
      </nav>
    </aside>
  );
}
