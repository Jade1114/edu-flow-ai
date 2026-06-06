import { createFileRoute } from "@tanstack/react-router";
import ClassGroupsPage from "../../pages/ClassGroupsPage";

export const Route = createFileRoute("/admin/class-groups")({
  component: ClassGroupsPage,
});
