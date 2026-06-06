import { createFileRoute } from "@tanstack/react-router";
import ModelTrainingPage from "../../pages/ModelTrainingPage";

export const Route = createFileRoute("/admin/model-training")({
  component: ModelTrainingPage,
});
