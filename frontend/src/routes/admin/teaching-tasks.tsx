import { createFileRoute } from "@tanstack/react-router";
import TeachingTasksPage from "../../pages/TeachingTasksPage";

export const Route = createFileRoute("/admin/teaching-tasks")({
  component: TeachingTasksPage,
});
