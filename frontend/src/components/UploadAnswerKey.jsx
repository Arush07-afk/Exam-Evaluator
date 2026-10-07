import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import {
  Paper, Typography, Button, Box, Alert, LinearProgress, Fade,
  Table, TableBody, TableCell, TableHead, TableRow
} from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import KeyIcon from "@mui/icons-material/VpnKey";
import { useSnackbar } from "notistack";
import { uploadAnswerKey } from "../api";
import { gradients } from "../theme";

export default function UploadAnswerKey({ paperId, onDone }) {
  const { enqueueSnackbar } = useSnackbar();
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);

  const onDrop = useCallback((accepted) => {
    if (accepted.length) setFile(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"], "image/*": [".png", ".jpg", ".jpeg"], "text/plain": [".txt"] },
    maxFiles: 1,
  });

  const handleSubmit = async () => {
    if (!paperId) {
      enqueueSnackbar("Upload a question paper first", { variant: "warning" });
      return;
    }
    if (!file) {
      enqueueSnackbar("Please select an answer key file", { variant: "warning" });
      return;
    }
    setLoading(true);
    try {
      const res = await uploadAnswerKey(file, paperId);
      setPreview(res.data.preview);
      enqueueSnackbar(`Parsed ${res.data.questions_keyed} answers`, { variant: "success" });
      onDone(res.data.key_id);
    } catch (err) {
      enqueueSnackbar(err.response?.data?.detail || "Upload failed", { variant: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper sx={{ p: { xs: 3, sm: 5 }, borderRadius: 5 }} elevation={0}>
      <Typography variant="h5" gutterBottom>🔑 Upload Answer Key</Typography>
      {!paperId && <Alert severity="warning" sx={{ mb: 3, borderRadius: 3 }}>Upload a question paper in Tab 1 first.</Alert>}

      <Box
        {...getRootProps()}
        sx={{
          border: "2px dashed",
          borderColor: isDragActive ? "secondary.main" : "#d7dbee",
          borderRadius: 4, p: 6, textAlign: "center", cursor: "pointer", mb: 3,
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
          {file ? <KeyIcon sx={{ fontSize: 34 }} /> : <CloudUploadIcon sx={{ fontSize: 34 }} />}
        </Box>
        <Typography sx={{ fontWeight: 600 }}>
          {file ? file.name : "Drag & drop the answer key here, or click to browse"}
        </Typography>
      </Box>

      <Fade in={loading}><LinearProgress sx={{ mb: 2, borderRadius: 2, height: 6 }} /></Fade>
      <Button variant="contained" color="secondary" size="large" onClick={handleSubmit} disabled={loading || !paperId}>
        Upload & Parse
      </Button>

      {preview && (
        <Box sx={{ mt: 4 }}>
          <Typography variant="h6" gutterBottom>✅ Parsed Answer Key Preview</Typography>
          <Table size="small" sx={{ "& tbody tr:hover": { bgcolor: "#f8f9fc" } }}>
            <TableHead>
              <TableRow><TableCell>Q#</TableCell><TableCell>Model Answer (excerpt)</TableCell><TableCell>Key Points</TableCell></TableRow>
            </TableHead>
            <TableBody>
              {Object.entries(preview).map(([qnum, v]) => (
                <TableRow key={qnum}>
                  <TableCell>{qnum}</TableCell>
                  <TableCell>{v.model_answer.slice(0, 120)}...</TableCell>
                  <TableCell>{v.key_points.length}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
    </Paper>
  );
}
