/**
 * MedFusion AI — Radiograph & DICOM Upload Component
 */

import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud, FileText, CheckCircle2, AlertTriangle, Eye } from "lucide-react";
import { imageService } from "../../services/images.service";
import { ImageType, ImageRecord } from "../../types";
import { LoadingSpinner } from "../common/LoadingSpinner";

interface RadiographUploaderProps {
  caseId?: string;
  onUploadSuccess: (image: ImageRecord) => void;
}

export const RadiographUploader: React.FC<RadiographUploaderProps> = ({
  caseId,
  onUploadSuccess,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageType, setImageType] = useState<ImageType>(ImageType.CHEST_XRAY_PA);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    const selected = acceptedFiles[0];
    if (!selected) return;
    setFile(selected);
    setUploadError(null);

    // If it's a standard web image, create a preview
    if (selected.type.startsWith("image/")) {
      const url = URL.createObjectURL(selected);
      setPreviewUrl(url);
    } else {
      // DICOM file (.dcm)
      setPreviewUrl(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
      "application/dicom": [".dcm"],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024, // 50MB
  });

  const handleUpload = async () => {
    if (!file || !caseId) return;
    setIsUploading(true);
    setUploadError(null);

    try {
      const res = await imageService.uploadImage(caseId, file, imageType);
      onUploadSuccess(res.image);
    } catch (err: any) {
      setUploadError(err?.response?.data?.detail || "Failed to ingest radiograph artifact.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-100 pb-3">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900">
            Medical Radiograph Ingestion
          </h3>
          <p className="text-xs text-gray-500">
            Upload DICOM (.dcm) or Standard Medical X-Ray (PNG / JPEG)
          </p>
        </div>
        <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 border border-blue-100">
          DenseNet Ingestion Ready
        </span>
      </div>

      {uploadError && (
        <div className="mt-4 flex items-center gap-2 rounded-xl bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800">
          <AlertTriangle className="h-4 w-4 text-rose-600 flex-shrink-0" />
          <span>{uploadError}</span>
        </div>
      )}

      {/* Metadata Form */}
      <div className="mt-4">
        <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
          Radiograph Acquisition &amp; Projection Type
        </label>
        <select
          value={imageType}
          onChange={(e) => setImageType(e.target.value as ImageType)}
          className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
        >
          <option value={ImageType.CHEST_XRAY_PA}>Chest X-Ray (PA Projection)</option>
          <option value={ImageType.CHEST_XRAY_AP}>Chest X-Ray (AP Projection)</option>
          <option value={ImageType.CHEST_CT_AXIAL}>Chest CT (Axial Slice)</option>
          <option value={ImageType.CHEST_CT_CORONAL}>Chest CT (Coronal Slice)</option>
          <option value={ImageType.OTHER}>Other Radiographic Modality</option>
        </select>
      </div>

      {/* Dropzone Container */}
      <div
        {...getRootProps()}
        className={`mt-4 flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 transition-colors cursor-pointer ${
          isDragActive
            ? "border-primary-500 bg-primary-50/50"
            : file
            ? "border-emerald-400 bg-emerald-50/30"
            : "border-gray-300 bg-gray-50 hover:bg-gray-100/60"
        }`}
      >
        <input {...getInputProps()} />

        {file ? (
          <div className="flex flex-col items-center text-center">
            {previewUrl ? (
              <div className="relative mb-3 h-28 w-28 overflow-hidden rounded-lg border border-gray-200 bg-black">
                <img
                  src={previewUrl}
                  alt="Radiograph preview"
                  className="h-full w-full object-contain"
                />
                <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1 text-[9px] text-white">
                  Preview
                </span>
              </div>
            ) : (
              <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-primary-100 text-primary-700">
                <FileText className="h-6 w-6" />
              </div>
            )}
            <p className="text-xs font-bold text-gray-800">{file.name}</p>
            <p className="text-[10px] text-gray-500">
              {(file.size / (1024 * 1024)).toFixed(2)} MB &bull; {file.type || "DICOM Stream"}
            </p>
            <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">
              <CheckCircle2 className="h-3 w-3" /> Ready for Upload
            </span>
          </div>
        ) : (
          <div className="flex flex-col items-center text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gray-200 text-gray-500">
              <UploadCloud className="h-6 w-6" />
            </div>
            <p className="mt-3 text-xs font-semibold text-gray-700">
              Drag & drop CXR/DICOM file, or <span className="text-primary-600 underline">browse files</span>
            </p>
            <p className="mt-1 text-[10px] text-gray-400">
              Supports .dcm, .png, .jpeg (Max 50MB) &bull; Automatic Quality Filtering
            </p>
          </div>
        )}
      </div>

      {/* Upload Action */}
      {file && (
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={handleUpload}
            disabled={isUploading}
            className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-primary-700 active:scale-95 disabled:opacity-50"
          >
            {isUploading ? (
              <LoadingSpinner size="sm" className="p-0 text-white" />
            ) : (
              <>
                <Eye className="h-3.5 w-3.5" />
                Upload & Ingest Radiograph
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
};
