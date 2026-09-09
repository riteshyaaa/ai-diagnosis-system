import { Routes, Route } from "react-router-dom";

/**
 * MedFusion AI — Root Application Component
 *
 * Routes and layouts will be added incrementally in subsequent phases.
 */
function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <div className="flex min-h-screen items-center justify-center">
            <div className="card max-w-lg text-center">
              <h1 className="text-3xl font-bold text-primary-700">
                MedFusion AI
              </h1>
              <p className="mt-2 text-gray-500">
                Multimodal Clinical Decision Support System
              </p>
              <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                ⚕️ AI-generated output is for clinical decision support and
                research purposes only. It is not a substitute for professional
                medical judgment.
              </p>
              <p className="mt-4 text-xs text-gray-400">v0.1.0 — Phase 1</p>
            </div>
          </div>
        }
      />
    </Routes>
  );
}

export default App;
