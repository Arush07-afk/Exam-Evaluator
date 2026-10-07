import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import {
  Paper, Typography, TextField, Button, Box, Grid, LinearProgress, Chip, Fade
} from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import DescriptionIcon from "@mui/icons-material/Description";
import { useSnackbar } from "notistack";
import { uploadQuestionPaper } from "../api";
import { gradients } from "../theme";

export default function UploadQuestionPaper({ onDone }) {
  const { enqueueSnackbar } = useSnackbar();
  const [file, setFile] = useState(null);
  const [totalMarks, setTotalMarks] = useState(80);
  const [subject, setSubject] = useState("English Core");
  const [examDate, setExamDate] = useState("");
  const [loading, setLoading] = useState(false);

  const onDrop = useCallback((accepted) => {
    if (accepted.length) setFile(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"], "image/*": [".png", ".jpg", ".jpeg"], "text/plain": [".txt"] },
    maxFiles: 1,
  });

  const handleSubmit = async () => {
    if (!file) {
      enqueueSnackbar("Please select a file first", { variant: "warning" });
      return;
    }
    setLoading(true);
    try {
      const res = await uploadQuestionPaper(file, totalMarks, subject, examDate);
      enqueueSnackbar(`Uploaded — ${res.data.questions_found} questions detected`, { variant: "success" });
      onDone(res.data.paper_id);
    } catch (err) {
      enqueueSnackbar(err.response?.data?.detail || "Upload failed", { variant: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper sx={{ p: { xs: 3, sm: 5 }, borderRadius: 5 }} elevation={0}>
      <Typography variant="h5" gutterBottom>📄 Upload Question Paper</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Drop in the exam paper to get started — we'll detect the questions automatically.
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Box
            {...getRootProps()}
            sx={{
              border: "2px dashed",
              borderColor: isDragActive ? "secondary.main" : "#d7dbee",
              borderRadius: 4,
              p: 6,
              textAlign: "center",
              cursor: "pointer",
              bgcolor: isDragActive ? "rgba(255,122,89,0.06)" : "#f8f9fc",
              transition: "all .25s ease",
              transform: isDragActive ? "scale(1.01)" : "scale(1)",
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
              {file ? <DescriptionIcon sx={{ fontSize: 34 }} /> : <CloudUploadIcon sx={{ fontSize: 34 }} />}
            </Box>
            <Typography sx={{ fontWeight: 600 }}>
              {file ? file.name : "Drag & drop the question paper here, or click to browse"}
            </Typography>
            {file && <Chip sx={{ mt: 1.5 }} label={`${(file.size / 1024).toFixed(0)} KB`} size="small" color="secondary" variant="outlined" />}
          </Box>
        </Grid>

        <Grid item xs={12} sm={4}>
          <TextField
            label="Total Marks" type="number" fullWidth
            value={totalMarks} onChange={(e) => setTotalMarks(e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <TextField label="Subject" fullWidth value={subject} onChange={(e) => setSubject(e.target.value)} />
        </Grid>
        <Grid item xs={12} sm={4}>
          <TextField
            label="Exam Date" type="date" fullWidth InputLabelProps={{ shrink: true }}
            value={examDate} onChange={(e) => setExamDate(e.target.value)}
          />
        </Grid>

        <Grid item xs={12}>
          <Fade in={loading}><LinearProgress sx={{ mb: 2, borderRadius: 2, height: 6 }} /></Fade>
          <Button variant="contained" color="secondary" size="large" onClick={handleSubmit} disabled={loading}>
            Upload & Parse
          </Button>
        </Grid>
      </Grid>
    </Paper>
  );
}
