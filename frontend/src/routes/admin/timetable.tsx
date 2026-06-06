import { createFileRoute } from "@tanstack/react-router";
import TimetablePage from "../../pages/TimetablePage";

export const Route = createFileRoute("/admin/timetable")({
  component: TimetablePage,
});
