import { createFileRoute } from "@tanstack/react-router";
import AdjustmentPage from "../../pages/AdjustmentPage";
export const Route = createFileRoute("/admin/adjustment")({ component: AdjustmentPage });
