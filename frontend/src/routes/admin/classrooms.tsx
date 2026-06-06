import { createFileRoute } from "@tanstack/react-router";
import ClassroomsPage from "../../pages/ClassroomsPage";

export const Route = createFileRoute("/admin/classrooms")({
  component: ClassroomsPage,
});
