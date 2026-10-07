import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import {
  Paper, Typography, Button, Box, Alert, LinearProgress, List, ListItem,
  ListItemText, Chip, Stack, Fade
} from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import FolderIcon from "@mui/icons-material/FolderOpen";
import { useSnackbar } from "notistack";
import { uploadAnswerSheets, evaluateBatch } from "../api";
import { gradients } from "../theme";

export default function UploadAnswerSheets({ paperId, keyId, onDone, onEvaluated }) {
  const { enqueueSnackbar } = useSnackbar();
  const [files, setFiles] = useState([]);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [uploadedSheets, setUploadedSheets] = useState([]);
  const [batchId, setBatchId] = useState(null);

  const onDrop = useCallback((accepted) => setFiles((prev) => [...prev, ...accepted]), []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"], "image/*": [".png", ".jpg", ".jpeg"], "text/plain": [".txt"] },
  });

  const handleUpload = async () => {
    if (!paperId || !keyId) {
      enqueueSnackbar("Complete the question paper and answer key steps first", { variant: "warning" });
      return;
    }
    if (!files.length) {
      enqueueSnackbar("Add at least one answer sheet", { variant: "warning" });
      return;
    }
    setUploading(true);
    setProgress(0);
    try {
      const res = await uploadAnswerSheets(files, paperId, keyId, setProgress);
      setUploadedSheets(res.data.sheets);
      setBatchId(res.data.batch_id);
      onDone(res.data.batch_id);
      enqueueSnackbar(`${res.data.sheets_uploaded} sheets uploaded`, { variant: "success" });
    } catch (err) {
      enqueueSnackbar(err.response?.data?.detail || "Upload failed", { variant: "error" });
    } finally {
      setUploading(false);
    }
  };

  const handleEvaluate = async () => {
    if (!batchId) return;
    setEvaluating(true);
    try {
      const res = await evaluateBatch(paperId, keyId, batchId);
      enqueueSnackbar(`Evaluated ${res.data.evaluated_count} sheets`, { variant: "success" });
      if (res.data.errors?.length) {
        enqueueSnackbar(`${res.data.errors.length} sheets failed to process`, { variant: "warning" });
      }
      onEvaluated();
    } catch (err) {
      enqueueSnackbar(err.response?.data?.detail || "Evaluation failed", { variant: "error" });
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <Paper sx={{ p: { xs: 3, sm: 5 }, borderRadius: 5 }} elevation={0}>
      <Typography variant="h5" gutterBottom>📚 Upload Answer Sheets (up to 50)</Typography>
      {(!paperId || !keyId) && (
        <Alert severity="warning" sx={{ mb: 3, borderRadius: 3 }}>Complete Tabs 1 & 2 before uploading answer sheets.</Alert>
      )}

      <Box
        {...getRootProps()}
        sx={{
          border: "2px dashed",
          borderColor: isDragActive ? "secondary.main" : "#d7dbee",
          borderRadius: 4, p: 6, textAlign: "center", cursor: "pointer", mb: 2,
          bgcolor: isDragActive ? "rgba(255,122,89,0.06)" : "#f8f9fc",
          transition: "all .25s ease",
          "&:hover": { borderColor: "primary.main", bgcolor: "rgba(102,126,234,0.05)" },
        }}
      >
        <input {...getInputProps()} />
        <Box
          sx={{
            width: 72, height: 72, mx: "auto", mb: 2, borderRadius: "50%",
            display: "flex", alignItems: "center", justifyContent: "center",
            background: gradients.card, color: "#fff",
            animation: isDragActive ? "pulse 1s infinite" : "none",
            "@keyframes pulse": { "0%": { transform: "scale(1)" }, "50%": { transform: "scale(1.1)" }, "100%": { transform: "scale(1)" } },
          }}
        >
          {files.length ? <FolderIcon sx={{ fontSize: 34 }} /> : <CloudUploadIcon sx={{ fontSize: 34 }} />}
        </Box>
        <Typography sx={{ fontWeight: 600 }}>Drag & drop multiple answer sheets here, or click to browse</Typography>
        <Typography variant="body2" color="text.secondary">{files.length} file(s) selected</Typography>
      </Box>

      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <Button variant="contained" color="secondary" onClick={handleUpload} disabled={uploading || !paperId || !keyId}>
          Upload All
        </Button>
        <Button variant="outlined" color="primary" onClick={handleEvaluate} disabled={!batchId || evaluating} sx={{ borderWidth: 2, "&:hover": { borderWidth: 2 } }}>
          {evaluating ? "Evaluating..." : "Run Evaluation"}
        </Button>
      </Stack>

      <Fade in={uploading}><LinearProgress variant="determinate" value={progress} sx={{ mb: 2, borderRadius: 2, height: 6 }} /></Fade>
      <Fade in={evaluating}><LinearProgress sx={{ mb: 2, borderRadius: 2, height: 6 }} /></Fade>

      {uploadedSheets.length > 0 && (
        <List dense sx={{ maxHeight: 300, overflow: "auto", bgcolor: "#f8f9fc", border: "1px solid #e8eaf6", borderRadius: 3, p: 1 }}>
          {uploadedSheets.map((s, i) => (
            <ListItem key={i} sx={{ borderRadius: 2, mb: 0.5, bgcolor: "#fff" }} secondaryAction={
              <Chip
                size="small"
                label={s.status === "uploaded" ? "✓ Uploaded" : s.status}
                color={s.status === "uploaded" ? "success" : "error"}
              />
            }>
              <ListItemText primary={s.filename} />
            </ListItem>
          ))}
        </List>
      )}
    </Paper>
  );
}
