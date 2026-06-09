import { Outlet, useLocation } from "@tanstack/react-router";
import AllocationManager from "../components/AllocationManager";

export default function AllocationPage() {
  const location = useLocation();
  if (location.pathname !== "/admin/allocation") return <Outlet />;
  return <AllocationManager />;
}
