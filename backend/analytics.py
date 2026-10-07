"""
analytics.py
Computes batch-level analytics (pass/fail, grade distribution, stats,
section-wise breakdown) and exports results to Excel.
"""
import statistics
from typing import List, Dict
import pandas as pd

PASS_PERCENTAGE = 33.0

SECTION_MAP = {
    # question number -> section name; extend/edit per actual paper layout
    "1": "Reading", "2": "Reading",
    "3": "Writing", "4": "Writing",
    "5": "Grammar", "6": "Grammar",
    "7": "Literature", "8": "Literature", "9": "Literature", "10": "Literature",
}


class AnalyticsEngine:
    def __init__(self, student_results: List[Dict]):
        """student_results: list of dicts with keys roll_number, percentage, grade,
        total_marks_awarded, total_max_marks, question_results."""
        self.results = student_results

    # ---------- Core stats ----------
    def pass_fail(self) -> Dict:
        passed = [r for r in self.results if r["percentage"] >= PASS_PERCENTAGE]
        failed = [r for r in self.results if r["percentage"] < PASS_PERCENTAGE]
        return {"passed": len(passed), "failed": len(failed), "total": len(self.results)}

    def grade_distribution(self) -> Dict[str, int]:
        dist = {g: 0 for g in ["A1", "A2", "B1", "B2", "C1", "C2", "D", "E"]}
        for r in self.results:
            dist[r["grade"]] = dist.get(r["grade"], 0) + 1
        return dist

    def score_statistics(self) -> Dict:
        scores = [r["percentage"] for r in self.results]
        if not scores:
            return {}
        sorted_scores = sorted(scores)
        return {
            "mean": round(statistics.mean(scores), 2),
            "median": round(statistics.median(scores), 2),
            "mode": round(statistics.mode(scores), 2) if len(set(scores)) < len(scores) else None,
            "std_dev": round(statistics.pstdev(scores), 2) if len(scores) > 1 else 0.0,
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "q1": round(sorted_scores[len(sorted_scores) // 4], 2),
            "q3": round(sorted_scores[(3 * len(sorted_scores)) // 4], 2),
        }

    def performance_bands(self) -> Dict[str, int]:
        bands = {"90-100": 0, "75-89": 0, "60-74": 0, "40-59": 0, "33-39": 0, "0-32": 0}
        for r in self.results:
            p = r["percentage"]
            if p >= 90:
                bands["90-100"] += 1
            elif p >= 75:
                bands["75-89"] += 1
            elif p >= 60:
                bands["60-74"] += 1
            elif p >= 40:
                bands["40-59"] += 1
            elif p >= 33:
                bands["33-39"] += 1
            else:
                bands["0-32"] += 1
        return bands

    def top_bottom_performers(self, n: int = 5) -> Dict[str, List[Dict]]:
        sorted_res = sorted(self.results, key=lambda r: r["percentage"], reverse=True)
        return {"top": sorted_res[:n], "bottom": sorted_res[-n:][::-1]}

    def section_wise_analysis(self) -> Dict[str, float]:
        """Average % score per section across all students."""
        section_totals: Dict[str, List[float]] = {}
        for r in self.results:
            for qnum, qres in r.get("question_results", {}).items():
                if not qres.get("counted", True):
                    continue
                section = SECTION_MAP.get(qnum.rstrip("abcdefghijklmnopqrstuvwxyz"), "Other")
                pct = (qres["marks_awarded"] / qres["max_marks"] * 100) if qres["max_marks"] else 0
                section_totals.setdefault(section, []).append(pct)
        return {sec: round(statistics.mean(vals), 2) for sec, vals in section_totals.items()}

    def full_report(self) -> Dict:
        return {
            "pass_fail": self.pass_fail(),
            "grade_distribution": self.grade_distribution(),
            "score_statistics": self.score_statistics(),
            "performance_bands": self.performance_bands(),
            "top_bottom": self.top_bottom_performers(),
            "section_wise": self.section_wise_analysis(),
        }

    # ---------- Excel export ----------
    def export_excel(self, file_path: str):
        rows = []
        for r in self.results:
            row = {
                "Roll Number": r["roll_number"],
                "Total Marks": r["total_marks_awarded"],
                "Max Marks": r["total_max_marks"],
                "Percentage": r["percentage"],
                "Grade": r["grade"],
                "Result": "Pass" if r["percentage"] >= PASS_PERCENTAGE else "Fail",
            }
            for qnum, qres in r.get("question_results", {}).items():
                row[f"Q{qnum}"] = qres["marks_awarded"]
            rows.append(row)
        df = pd.DataFrame(rows)

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Results", index=False)

            summary = self.full_report()
            summary_rows = [
                ["Total Students", summary["pass_fail"]["total"]],
                ["Passed", summary["pass_fail"]["passed"]],
                ["Failed", summary["pass_fail"]["failed"]],
                ["Mean %", summary["score_statistics"].get("mean")],
                ["Median %", summary["score_statistics"].get("median")],
                ["Std Dev", summary["score_statistics"].get("std_dev")],
                ["Highest %", summary["score_statistics"].get("max")],
                ["Lowest %", summary["score_statistics"].get("min")],
            ]
            pd.DataFrame(summary_rows, columns=["Metric", "Value"]).to_excel(
                writer, sheet_name="Summary", index=False
            )
        return file_path