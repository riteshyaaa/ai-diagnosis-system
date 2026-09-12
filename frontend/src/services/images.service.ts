/**
 * MedFusion AI — Medical Images API Service
 */

import api from "./api";
import { ImageType } from "../types";
import type {
  ImageListResponse,
  ImageRecord,
  ImageUploadResponse,
} from "../types";

export const imageService = {
  /**
   * Upload a radiograph or medical image (DICOM / PNG / JPEG) to a diagnostic case.
   */
  async uploadImage(
    caseId: string,
    file: File,
    imageType: ImageType = ImageType.CHEST_XRAY_PA
  ): Promise<ImageUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("image_type", imageType);

    const { data } = await api.post<ImageUploadResponse>(
      `/cases/${caseId}/images`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return data;
  },

  /**
   * Fetch image metadata record by ID.
   */
  async getImageById(imageId: string): Promise<ImageRecord> {
    const { data } = await api.get<ImageRecord>(`/images/${imageId}`);
    return data;
  },

  /**
   * Fetch all images associated with a specific case.
   */
  async getImagesByCase(caseId: string): Promise<ImageListResponse> {
    const { data } = await api.get<ImageListResponse>(`/cases/${caseId}/images`);
    return data;
  },

  /**
   * Get raw or processed image download URL.
   */
  getImageDownloadUrl(imageId: string): string {
    const baseUrl = api.defaults.baseURL || "http://localhost:8000/api/v1";
    return `${baseUrl}/images/${imageId}/file`;
  },
};
