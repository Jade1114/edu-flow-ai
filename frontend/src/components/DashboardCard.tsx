import { useAtomValue } from "jotai";
import { displayNameAtom, isAdminAtom } from "../atoms/auth";

export default function DashboardCard() {
  const displayName = useAtomValue(displayNameAtom);
  const isAdmin = useAtomValue(isAdminAtom);

  return (
    <div>
      <h2>欢迎使用教务管理系统</h2>
      <div className="card bg-base-100 shadow-sm mt-5">
        <div className="card-body">
          <p>当前用户：{displayName}</p>
          <p>角色：{isAdmin ? "教务管理员" : "教师"}</p>
          <p className="mt-4 text-base-content/50">
            请从左侧菜单选择功能模块进行操作。
          </p>
        </div>
      </div>
    </div>
  );
}
