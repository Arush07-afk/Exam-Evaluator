import React, { useEffect, useState, useMemo } from "react";
import {
  Paper, Typography, TextField, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TableSortLabel, Button, Box, Dialog, DialogTitle,
  DialogContent, Alert, Chip, Stack
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import BarChartIcon from "@mui/icons-material/BarChart";
import { useSnackbar } from "notistack";
import { getResults, exportUrl } from "../api";

const PASS_PCT = 33;

export default function EvaluationResults({ batchId, evaluated, onViewAnalytics }) {
  const { enqueueSnackbar } = useSnackbar();
  const [results, setResults] = useState([]);
  const [search, setSearch] = useState("");
  const [orderBy, setOrderBy] = useState("percentage");
  const [order, setOrder] = useState("desc");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!batchId || !evaluated) return;
    getResults(batchId)
      .then((res) => setResults(res.data.results))
      .catch((err) => enqueueSnackbar(err.response?.data?.detail || "Failed to load results", { variant: "error" }));
  }, [batchId, evaluated]);

  const filtered = useMemo(() => {
    let rows = results.filter((r) => r.roll_number.toLowerCase().includes(search.toLowerCase()));
    rows.sort((a, b) => {
      const va = a[orderBy], vb = b[orderBy];
      if (va < vb) return order === "asc" ? -1 : 1;
      if (va > vb) return order === "asc" ? 1 : -1;
      return 0;
    });
    return rows;
  }, [results, search, orderBy, order]);

  const handleSort = (col) => {
    if (orderBy === col) setOrder(order === "asc" ? "desc" : "asc");
    else { setOrderBy(col); setOrder("asc"); }
  };

  if (!batchId || !evaluated) {
    return <Alert severity="info" sx={{ borderRadius: 3 }}>Upload and evaluate answer sheets to see results here.</Alert>;
  }

  const passCount = results.filter((r) => r.percentage >= PASS_PCT).length;

  return (
    <Paper sx={{ p: { xs: 3, sm: 4 }, borderRadius: 5 }} elevation={0}>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} spacing={2} sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h5">✅ Evaluation Results</Typography>
          <Typography variant="body2" color="text.secondary">
            {filtered.length} students · {passCount} passed · {results.length - passCount} need support
          </Typography>
        </Box>
        <Stack direction="row" spacing={1.5}>
          <Button variant="outlined" startIcon={<BarChartIcon />} onClick={onViewAnalytics} sx={{ borderWidth: 2, "&:hover": { borderWidth: 2 } }}>
            Analytics
          </Button>
          <Button variant="contained" color="secondary" startIcon={<DownloadIcon />} href={exportUrl(batchId)}>
            Export Excel
          </Button>
        </Stack>
      </Stack>

      <TextField
        label="Search Roll Number" size="small" fullWidth sx={{ mb: 2 }}
        value={search} onChange={(e) => setSearch(e.target.value)}
      />

      <TableContainer sx={{ borderRadius: 3, border: "1px solid #eef0f9" }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: "#f8f9fc" }}>
              {["roll_number", "total_marks_awarded", "percentage", "grade"].map((col) => (
                <TableCell key={col} sx={{ fontWeight: 700 }}>
                  <TableSortLabel active={orderBy === col} direction={order} onClick={() => handleSort(col)}>
                    {col.replace(/_/g, " ")}
                  </TableSortLabel>
                </TableCell>
              ))}
              <TableCell sx={{ fontWeight: 700 }}>Result</TableCell>
              <TableCell sx={{ fontWeight: 700 }}>Details</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filtered.map((r, i) => {
              const pass = r.percentage >= PASS_PCT;
              return (
                <TableRow
                  key={i}
                  sx={{
                    transition: "background .15s ease",
                    "&:nth-of-type(odd)": { bgcolor: "#fbfbfe" },
                    "&:hover": { bgcolor: "#f0f1fb" },
                  }}
                >
                  <TableCell sx={{ fontWeight: 600 }}>{r.roll_number}</TableCell>
                  <TableCell>{r.total_marks_awarded} / {r.total_max_marks}</TableCell>
                  <TableCell>{r.percentage}%</TableCell>
                  <TableCell>
                    <Chip size="small" label={r.grade} sx={{ bgcolor: "#eef0fd", color: "#4c53b4" }} />
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={pass ? "Pass" : "Fail"} color={pass ? "success" : "error"} sx={{ opacity: 0.9 }} />
                  </TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => setSelected(r)}>View</Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={!!selected} onClose={() => setSelected(null)} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: 4 } }}>
        <DialogTitle sx={{ fontWeight: 700 }}>Student {selected?.roll_number} — Question Breakdown</DialogTitle>
        <DialogContent>
          {selected && (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Q#</TableCell><TableCell>Marks</TableCell><TableCell>Content</TableCell>
                  <TableCell>Org.</TableCell><TableCell>Language</TableCell><TableCell>Grammar</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {Object.entries(selected.question_results).map(([q, v]) => (
                  <TableRow key={q}>
                    <TableCell>{q}</TableCell>
                    <TableCell>{v.marks_awarded}/{v.max_marks}</TableCell>
                    <TableCell>{v.content_score}%</TableCell>
                    <TableCell>{v.organization_score}%</TableCell>
                    <TableCell>{v.language_score}%</TableCell>
                    <TableCell>{v.grammar_score}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </DialogContent>
      </Dialog>
    </Paper>
  );
}
