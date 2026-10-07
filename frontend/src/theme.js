import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    primary: { main: "#667eea", dark: "#5a3fa0", light: "#8fa4f3", contrastText: "#fff" },
    secondary: { main: "#ff7a59", dark: "#e85d3d", contrastText: "#fff" },
    success: { main: "#4caf82" },
    error: { main: "#e5686f" },
    background: { default: "#f8f9fc", paper: "#ffffff" },
    text: { primary: "#1f2138", secondary: "#6b7089" },
  },
  shape: { borderRadius: 16 },
  typography: {
    fontFamily: '"Inter", "Segoe UI", Roboto, Arial, sans-serif',
    h5: { fontWeight: 800 },
    h6: { fontWeight: 700 },
    button: { fontWeight: 700, textTransform: "none" },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: { boxShadow: "0 4px 24px rgba(80, 63, 205, 0.06)" },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 12, padding: "10px 22px" },
        containedSecondary: {
          background: "linear-gradient(135deg, #ff7a59 0%, #ff9a5a 100%)",
          boxShadow: "0 6px 16px rgba(255, 122, 89, 0.35)",
          "&:hover": { boxShadow: "0 8px 20px rgba(255, 122, 89, 0.45)" },
        },
      },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 700, borderRadius: 999 } } },
  },
});

export const gradients = {
  header: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  card: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  coral: "linear-gradient(135deg, #ff7a59 0%, #ff9a5a 100%)",
  success: "linear-gradient(135deg, #4caf82 0%, #6fd3a3 100%)",
};

export default theme;
