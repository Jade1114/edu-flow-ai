import { createFileRoute } from "@tanstack/react-router";
import CoursesPage from "../../pages/CoursesPage";

export const Route = createFileRoute("/admin/courses")({
  component: CoursesPage,
});
