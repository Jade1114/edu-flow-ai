import { createFileRoute } from "@tanstack/react-router";
import ImportReviewPage from "../../pages/ImportReviewPage";

export const Route = createFileRoute("/admin/import-review")({
  component: ImportReviewPage,
});
