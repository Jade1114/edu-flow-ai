import { createFileRoute } from "@tanstack/react-router";
import AllocationPage from "../../pages/AllocationPage";
export const Route = createFileRoute("/admin/allocation")({ component: AllocationPage });
