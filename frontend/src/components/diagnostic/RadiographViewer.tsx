/**
 * MedFusion AI — Interactive Radiograph Viewer with Grad-CAM Heatmap Blending & Attention Overlays
 */

import React, { useState } from "react";
import {
  Layers,
  Sliders,
  RefreshCw,
  Eye,
  EyeOff,
  Maximize2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { VisualExplanationResponse, ImageRecord } from "../../types";
import { explanationService } from "../../services/explanations.service";
import { imageService } from "../../services/images.service";
import { LoadingSpinner } from "../common/LoadingSpinner";

interface RadiographViewerProps {
  image?: ImageRecord | null;
  visualExplanation?: VisualExplanationResponse | null;
  predictionId?: string;
  onGradCamUpdated?: (updated: VisualExplanationResponse) => void;
}

const THORACIC_PATHOLOGIES = [
  "Atelectasis",
  "Cardiomegaly",
  "Effusion",
  "Infiltration",
  "Mass",
];

export const RadiographViewer: React.FC<RadiographViewerProps> = ({
  image,
  visualExplanation,
  predictionId,
  onGradCamUpdated,
}) => {
  const [opacity, setOpacity] = useState<number>(55); // 0 - 100
  const [showHeatmap, setShowHeatmap] = useState<boolean>(true);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState<boolean>(true);
  const [selectedPathology, setSelectedPathology] = useState<string>("Cardiomegaly");
  const [isRecalculating, setIsRecalculating] = useState<boolean>(false);
  const [zoomLevel, setZoomLevel] = useState<number>(1);

  const rawImageUrl = image?.id
    ? imageService.getImageDownloadUrl(image.id)
    : "https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&w=800&q=80";

  // Check if visual explanation has heatmap data
  const heatmapData = visualExplanation?.heatmap_base64
    ? visualExplanation.heatmap_base64.startsWith("data:")
      ? visualExplanation.heatmap_base64
      : `data:image/png;base64,${visualExplanation.heatmap_base64}`
    : visualExplanation?.heatmap_url || null;

  const boundingBoxes = visualExplanation?.attention_regions || [];

  const handleRecalculate = async () => {
    if (!predictionId) return;
    setIsRecalculating(true);
    try {
      const response = await explanationService.recalculatePathologySaliency(predictionId, {
        target_pathology: selectedPathology,
      });
      if (onGradCamUpdated) {
        onGradCamUpdated(response);
      }
    } catch (err) {
      console.error("Failed to recalculate Grad-CAM saliency:", err);
    } finally {
      setIsRecalculating(false);
    }
  };

  return (
    <div className="flex flex-col rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Viewer Header */}
      <div className="flex flex-wrap items-center justify-between border-b border-gray-100 bg-gray-50/75 px-4 py-3 gap-2">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-primary-600" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-gray-800">
            Explainable Radiograph Workstation (Grad-CAM Saliency)
          </h3>
        </div>

        {/* View Controls */}
        <div className="flex items-center gap-3">
          {/* Zoom controls */}
          <div className="flex items-center rounded-lg border border-gray-200 bg-white p-0.5">
            <button
              onClick={() => setZoomLevel((z) => Math.max(0.75, z - 0.25))}
              className="p-1 text-gray-500 hover:text-gray-900 rounded"
              title="Zoom Out"
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </button>
            <span className="px-1.5 text-[10px] font-bold text-gray-600">
              {Math.round(zoomLevel * 100)}%
            </span>
            <button
              onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.25))}
              className="p-1 text-gray-500 hover:text-gray-900 rounded"
              title="Zoom In"
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Toggle Heatmap */}
          <button
            type="button"
            onClick={() => setShowHeatmap((prev) => !prev)}
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold transition-colors ${
              showHeatmap
                ? "border-primary-200 bg-primary-50 text-primary-700"
                : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            {showHeatmap ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
            <span>Heatmap Overlay</span>
          </button>

          {/* Toggle Bounding Boxes */}
          <button
            type="button"
            onClick={() => setShowBoundingBoxes((prev) => !prev)}
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold transition-colors ${
              showBoundingBoxes
                ? "border-purple-200 bg-purple-50 text-purple-700"
                : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            <Maximize2 className="h-3.5 w-3.5" />
            <span>Attention ROI</span>
          </button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="relative flex min-h-[420px] max-h-[560px] items-center justify-center overflow-hidden bg-slate-950 p-4 select-none">
        <div
          className="relative inline-block transition-transform duration-150"
          style={{ transform: `scale(${zoomLevel})` }}
        >
          {/* Base Radiograph */}
          <img
            src={rawImageUrl}
            alt="Thoracic Radiograph"
            className="max-h-[500px] w-auto rounded-lg object-contain"
          />

          {/* Grad-CAM Heatmap Layer */}
          {showHeatmap && heatmapData && (
            <img
              src={heatmapData}
              alt="Grad-CAM Saliency Heatmap"
              className="pointer-events-none absolute inset-0 h-full w-full rounded-lg object-contain mix-blend-screen transition-opacity duration-200"
              style={{ opacity: opacity / 100 }}
            />
          )}

          {/* Bounding Box Attention Overlays */}
          {showBoundingBoxes &&
            boundingBoxes.map((box, idx) => {
              const [ymin, xmin, ymax, xmax] = box.box;
              const top = `${ymin * 100}%`;
              const left = `${xmin * 100}%`;
              const width = `${(xmax - xmin) * 100}%`;
              const height = `${(ymax - ymin) * 100}%`;
              const label = box.associated_pathology || box.anatomical_region || "ROI";

              return (
                <div
                  key={idx}
                  className="pointer-events-none absolute border-2 border-dashed border-amber-400 bg-amber-400/10 transition-all"
                  style={{ top, left, width, height }}
                >
                  <span className="absolute -top-5 left-0 rounded bg-amber-500 px-1.5 py-0.5 text-[9px] font-black uppercase text-slate-950 shadow-md">
                    {label} ({(box.saliency_score * 100).toFixed(0)}%)
                  </span>
                </div>
              );
            })}
        </div>

        {/* DenseNet Activation Indicator */}
        <div className="absolute bottom-3 left-3 rounded-lg bg-black/80 px-2.5 py-1 text-[10px] font-medium text-emerald-400 backdrop-blur border border-emerald-500/30 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          DenseNet-121 Feature Map: conv5_block16_concat
        </div>
      </div>

      {/* Control Footer Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-t border-gray-100 bg-gray-50/50 p-4">
        {/* Opacity Slider */}
        <div className="flex items-center gap-3 min-w-[240px]">
          <Sliders className="h-4 w-4 text-gray-500" />
          <span className="text-xs font-semibold text-gray-700">Heatmap Opacity:</span>
          <input
            type="range"
            min={0}
            max={100}
            value={opacity}
            disabled={!showHeatmap}
            onChange={(e) => setOpacity(Number(e.target.value))}
            className="h-1.5 flex-1 cursor-pointer appearance-none rounded-lg bg-gray-200 accent-primary-600 disabled:opacity-40"
          />
          <span className="w-8 text-right text-xs font-bold text-gray-700">{opacity}%</span>
        </div>

        {/* Recalculate Saliency for Alternative Pathology */}
        {predictionId && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Target Pathology:</span>
            <select
              value={selectedPathology}
              onChange={(e) => setSelectedPathology(e.target.value)}
              className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs font-semibold text-gray-800 focus:border-primary-500 focus:outline-none"
            >
              {THORACIC_PATHOLOGIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleRecalculate}
              disabled={isRecalculating}
              className="inline-flex items-center gap-1.5 rounded-lg bg-gray-900 px-3 py-1 text-xs font-bold text-white hover:bg-gray-800 active:scale-95 disabled:opacity-50"
            >
              {isRecalculating ? (
                <LoadingSpinner size="sm" className="p-0 text-white" />
              ) : (
                <>
                  <RefreshCw className="h-3 w-3" />
                  Recalculate Grad-CAM
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
