import React, { useEffect, useState } from "react";
import { Grid, Paper, Typography, Alert, Table, TableBody, TableCell, TableHead, TableRow, Box, Button, Stack } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from "recharts";
import { useSnackbar } from "notistack";
import { getDashboard, exportUrl } from "../api";
import { gradients } from "../theme";

const PASS_COLORS = ["#4caf82", "#e5686f"];
const GRADE_COLOR = "#667eea";

function StatCard({ label, value, gradient }) {
  return (
    <Paper
      sx={{
        p: 2.5, textAlign: "center", borderRadius: 4, color: "#fff",
        background: gradient || "linear-gradient(135deg, #a1a6c4 0%, #7b81a8 100%)",
      }}
      elevation={0}
    >
      <Typography variant="body2" sx={{ opacity: 0.85 }}>{label}</Typography>
      <Typography variant="h5" sx={{ fontWeight: 800 }}>{value}</Typography>
    </Paper>
  );
}

export default function AnalyticsDashboard({ batchId, evaluated }) {
  const { enqueueSnackbar } = useSnackbar();
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!batchId || !evaluated) return;
    getDashboard(batchId)
      .then((res) => setData(res.data))
      .catch((err) => enqueueSnackbar(err.response?.data?.detail || "Failed to load analytics", { variant: "error" }));
  }, [batchId, evaluated]);

  if (!batchId || !evaluated) {
    return <Alert severity="info" sx={{ borderRadius: 3 }}>Evaluate a batch to see analytics here.</Alert>;
  }
  if (!data) return <Typography>Loading analytics...</Typography>;

  const pieData = [
    { name: "Passed", value: data.pass_fail.passed },
    { name: "Failed", value: data.pass_fail.failed },
  ];
  const gradeData = Object.entries(data.grade_distribution).map(([grade, count]) => ({ grade, count }));
  const bandData = Object.entries(data.performance_bands).map(([band, count]) => ({ band, count }));
  const sectionData = Object.entries(data.section_wise).map(([section, score]) => ({ section, score }));
  const stats = data.score_statistics;

  return (
    <Box>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} spacing={2} sx={{ mb: 3 }}>
        <Typography variant="h5">📊 Analytics</Typography>
        <Button variant="contained" color="secondary" startIcon={<DownloadIcon />} href={exportUrl(batchId)}>
          Download Report
        </Button>
      </Stack>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} sm={2}><StatCard label="Total" value={data.pass_fail.total} gradient={gradients.card} /></Grid>
        <Grid item xs={6} sm={2}><StatCard label="Passed" value={data.pass_fail.passed} gradient={gradients.success} /></Grid>
        <Grid item xs={6} sm={2}><StatCard label="Failed" value={data.pass_fail.failed} gradient="linear-gradient(135deg, #e5686f 0%, #f09199 100%)" /></Grid>
        <Grid item xs={6} sm={2}><StatCard label="Average %" value={stats.mean} gradient={gradients.coral} /></Grid>
        <Grid item xs={6} sm={2}><StatCard label="Highest %" value={stats.max} gradient={gradients.success} /></Grid>
        <Grid item xs={6} sm={2}><StatCard label="Lowest %" value={stats.min} gradient="linear-gradient(135deg, #e5686f 0%, #f09199 100%)" /></Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 4 }} elevation={0}>
            <Typography variant="h6" gutterBottom>Pass / Fail</Typography>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} paddingAngle={3} label>
                  {pieData.map((_, i) => <Cell key={i} fill={PASS_COLORS[i]} />)}
                </Pie>
                <Tooltip /><Legend />
              </PieChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 4 }} elevation={0}>
            <Typography variant="h6" gutterBottom>Grade Distribution</Typography>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={gradeData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="grade" /><YAxis /><Tooltip />
                <Bar dataKey="count" fill={GRADE_COLOR} radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 4 }} elevation={0}>
            <Typography variant="h6" gutterBottom>Score Distribution</Typography>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={bandData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="band" /><YAxis /><Tooltip />
                <Bar dataKey="count" fill="#ff7a59" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 4 }} elevation={0}>
            <Typography variant="h6" gutterBottom>Section-wise Performance</Typography>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={sectionData}>
                <PolarGrid /><PolarAngleAxis dataKey="section" /><PolarRadiusAxis domain={[0, 100]} />
                <Radar dataKey="score" stroke={GRADE_COLOR} fill={GRADE_COLOR} fillOpacity={0.5} />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 4 }} elevation={0}>
            <Typography variant="h6" gutterBottom>🏆 Top 5 Performers</Typography>
            <Table size="small">
              <TableHead><TableRow><TableCell>Roll No</TableCell><TableCell>%</TableCell><TableCell>Grade</TableCell></TableRow></TableHead>
              <TableBody>
                {data.top_bottom.top.map((r, i) => (
                  <TableRow key={i} sx={{ "&:hover": { bgcolor: "#f8f9fc" } }}><TableCell>{r.roll_number}</TableCell><TableCell>{r.percentage}%</TableCell><TableCell>{r.grade}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 4 }} elevation={0}>
            <Typography variant="h6" gutterBottom>🌱 Needs Improvement (Bottom 5)</Typography>
            <Table size="small">
              <TableHead><TableRow><TableCell>Roll No</TableCell><TableCell>%</TableCell><TableCell>Grade</TableCell></TableRow></TableHead>
              <TableBody>
                {data.top_bottom.bottom.map((r, i) => (
                  <TableRow key={i} sx={{ "&:hover": { bgcolor: "#f8f9fc" } }}><TableCell>{r.roll_number}</TableCell><TableCell>{r.percentage}%</TableCell><TableCell>{r.grade}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
