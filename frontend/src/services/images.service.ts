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
    imageType?: ImageType
  ): Promise<ImageUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (imageType) formData.append("image_type", imageType);

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

  /** Download an authorized image variant with the shared bearer-token client. */
  async downloadImage(imageId: string, signal?: AbortSignal): Promise<Blob> {
    const { data } = await api.get<Blob>(`/images/${imageId}/file`, {
      params: { variant: "processed" },
      responseType: "blob",
      signal,
    });
    return data;
  },

  /**
   * Fetch all images associated with a specific case.
   */
  async getImagesByCase(caseId: string): Promise<ImageListResponse> {
    const { data } = await api.get<ImageListResponse>(`/cases/${caseId}/images`);
    return data;
  },

};
