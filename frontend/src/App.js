import React, { useState } from "react";
import { Toolbar, Typography, Tabs, Tab, Container, Box, Chip, Fade } from "@mui/material";
import SchoolIcon from "@mui/icons-material/School";
import UploadQuestionPaper from "./components/UploadQuestionPaper";
import UploadAnswerKey from "./components/UploadAnswerKey";
import UploadAnswerSheets from "./components/UploadAnswerSheets";
import EvaluationResults from "./components/EvaluationResults";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import { gradients } from "./theme";

function TabPanel({ children, value, index }) {
  return value === index ? <Fade in timeout={400}><Box sx={{ py: 4 }}>{children}</Box></Fade> : null;
}

const STEPS = [
  { label: "Question Paper", emoji: "📄" },
  { label: "Answer Key", emoji: "🔑" },
  { label: "Answer Sheets", emoji: "📚" },
  { label: "Results", emoji: "✅" },
  { label: "Analytics", emoji: "📊" },
];

export default function App() {
  const [tab, setTab] = useState(0);

  // Shared workflow state across tabs
  const [paperId, setPaperId] = useState(null);
  const [keyId, setKeyId] = useState(null);
  const [batchId, setBatchId] = useState(null);
  const [evaluated, setEvaluated] = useState(false);

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <Box sx={{ background: gradients.header, color: "#fff", borderRadius: "0 0 28px 28px", boxShadow: "0 8px 32px rgba(102,126,234,0.35)" }}>
        <Container maxWidth="lg">
          <Toolbar disableGutters sx={{ py: 2 }}>
            <Box sx={{ width: 44, height: 44, borderRadius: "14px", bgcolor: "rgba(255,255,255,0.18)", display: "flex", alignItems: "center", justifyContent: "center", mr: 1.5, backdropFilter: "blur(6px)" }}>
              <SchoolIcon />
            </Box>
            <Box sx={{ flexGrow: 1 }}>
              <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1.2 }}>
                English Core Paper Evaluator
              </Typography>
              <Typography variant="caption" sx={{ opacity: 0.85 }}>
                Step {tab + 1} of {STEPS.length} · {STEPS[tab].label}
              </Typography>
            </Box>
            {paperId && <Chip label="Paper ✓" size="small" sx={{ mr: 1, bgcolor: "rgba(255,255,255,0.2)", color: "#fff" }} />}
            {keyId && <Chip label="Key ✓" size="small" sx={{ mr: 1, bgcolor: "rgba(255,255,255,0.2)", color: "#fff" }} />}
            {batchId && <Chip label="Sheets ✓" size="small" sx={{ bgcolor: "rgba(255,255,255,0.2)", color: "#fff" }} />}
          </Toolbar>

          <Tabs
            value={tab}
            onChange={(e, v) => setTab(v)}
            variant="fullWidth"
            TabIndicatorProps={{ style: { display: "none" } }}
            sx={{
              minHeight: 44,
              "& .MuiTab-root": {
                color: "rgba(255,255,255,0.75)",
                minHeight: 44,
                borderRadius: "999px",
                mx: 0.5,
                mb: 1.5,
                fontSize: 13,
                transition: "all .25s ease",
              },
              "& .Mui-selected": {
                color: "#fff !important",
                bgcolor: "rgba(255,255,255,0.18)",
                backdropFilter: "blur(6px)",
              },
            }}
          >
            {STEPS.map((s, i) => (
              <Tab key={i} label={`${s.emoji} ${s.label}`} />
            ))}
          </Tabs>
        </Container>
      </Box>

      <Container maxWidth="lg">
        <TabPanel value={tab} index={0}>
          <UploadQuestionPaper onDone={(id) => { setPaperId(id); setTab(1); }} />
        </TabPanel>

        <TabPanel value={tab} index={1}>
          <UploadAnswerKey paperId={paperId} onDone={(id) => { setKeyId(id); setTab(2); }} />
        </TabPanel>

        <TabPanel value={tab} index={2}>
          <UploadAnswerSheets
            paperId={paperId}
            keyId={keyId}
            onDone={(id) => { setBatchId(id); }}
            onEvaluated={() => { setEvaluated(true); setTab(3); }}
          />
        </TabPanel>

        <TabPanel value={tab} index={3}>
          <EvaluationResults batchId={batchId} evaluated={evaluated} onViewAnalytics={() => setTab(4)} />
        </TabPanel>

        <TabPanel value={tab} index={4}>
          <AnalyticsDashboard batchId={batchId} evaluated={evaluated} />
        </TabPanel>
      </Container>

      <Box component="footer" sx={{ textAlign: "center", color: "text.secondary", py: 4, fontSize: 13 }}>
        Made with 💜 for English Core Paper Evaluation
      </Box>
    </Box>
  );
}
