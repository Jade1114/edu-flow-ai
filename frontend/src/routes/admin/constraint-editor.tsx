import { createFileRoute } from "@tanstack/react-router";
import ConstraintEditorPage from "../../pages/ConstraintEditorPage";
export const Route = createFileRoute("/admin/constraint-editor")({ component: ConstraintEditorPage });
