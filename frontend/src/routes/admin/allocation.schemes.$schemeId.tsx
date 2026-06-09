import { createFileRoute } from "@tanstack/react-router";
import AllocationSchemeDetailPage from "../../pages/AllocationSchemeDetailPage";

export const Route = createFileRoute("/admin/allocation/schemes/$schemeId")({
  component: AllocationSchemeDetailPage,
});
