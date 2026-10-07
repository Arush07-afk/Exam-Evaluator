import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: API_BASE });

export const uploadQuestionPaper = (file, totalMarks, subject, examDate) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("total_marks", totalMarks);
  fd.append("subject", subject);
  fd.append("exam_date", examDate);
  return api.post("/api/upload/question-paper", fd);
};

export const uploadAnswerKey = (file, paperId) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("paper_id", paperId);
  return api.post("/api/upload/answer-key", fd);
};

export const uploadAnswerSheets = (files, paperId, keyId, onProgress) => {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  fd.append("paper_id", paperId);
  fd.append("key_id", keyId);
  return api.post("/api/upload/answer-sheets", fd, {
    onUploadProgress: (evt) => onProgress && onProgress(Math.round((evt.loaded * 100) / evt.total)),
  });
};

export const evaluateBatch = (paperId, keyId, batchId) => {
  const fd = new FormData();
  fd.append("batch_id", batchId);
  return api.post(`/api/evaluate/${paperId}/${keyId}`, fd);
};

export const getResults = (batchId) => api.get(`/api/results/${batchId}`);
export const getDashboard = (batchId) => api.get(`/api/dashboard/${batchId}`);
export const exportUrl = (batchId) => `${API_BASE}/api/export/${batchId}`;
