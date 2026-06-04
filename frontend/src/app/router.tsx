import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { CalibrationDatasetPage } from "../pages/CalibrationDatasetPage";
import { EvaluationWizardPage } from "../pages/EvaluationWizardPage";
import { HomePage } from "../pages/HomePage";
import { QuickEvaluationPage } from "../pages/QuickEvaluationPage";
import { RunDetailPage } from "../pages/RunDetailPage";
import { RunHistoryPage } from "../pages/RunHistoryPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <HomePage />
      },
      {
        path: "/quick-evaluation",
        element: <QuickEvaluationPage />
      },
      {
        path: "/evaluation",
        element: <EvaluationWizardPage />
      },
      {
        path: "/calibration",
        element: <CalibrationDatasetPage />
      },
      {
        path: "/history",
        element: <RunHistoryPage />
      },
      {
        path: "/runs/:runId",
        element: <RunDetailPage />
      }
    ]
  }
]);
