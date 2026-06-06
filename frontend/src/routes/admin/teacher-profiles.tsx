import { createFileRoute } from "@tanstack/react-router";
import TeacherProfilesPage from "../../pages/TeacherProfilesPage";
export const Route = createFileRoute("/admin/teacher-profiles")({ component: TeacherProfilesPage });
