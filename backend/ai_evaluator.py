"""
ai_evaluator.py
Parses question papers / answer keys and evaluates student answers using
semantic similarity (Sentence Transformers) plus CBSE-style rubric scoring.
"""
import re
import difflib
from typing import Dict, List
from sentence_transformers import SentenceTransformer, util

try:
    import language_tool_python
    _LT_AVAILABLE = True
except Exception:
    _LT_AVAILABLE = False


class AIEvaluator:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.grammar_tool = None
        if _LT_AVAILABLE:
            try:
                self.grammar_tool = language_tool_python.LanguageTool("en-US")
            except Exception:
                self.grammar_tool = None

        # CBSE rubric weights (organization = length/format)
        self.weights = {
            "content": 0.45,
            "organization": 0.25,
            "language": 0.20,
            "grammar": 0.10,
        }

    # Cosine range mapped to 0..1 (raw MiniLM similarity of unrelated text is ~0.2)
    SEM_LOW, SEM_HIGH = 0.25, 0.80
    LEN_MULT = 4  # expected words = model-answer words x this (capped at marks x 15)
    _STOP = {"the", "a", "an", "in", "on", "at", "to", "of", "for", "is", "are", "was", "were", "and", "or",
             "but", "that", "this", "with", "from", "has", "have", "had", "it", "its", "as", "by", "be",
             "those", "who", "which", "their", "his", "her", "they", "he", "she", "can", "will", "any", "like"}

    # ---------- Parsing ----------
    def parse_questions(self, text: str) -> Dict[str, Dict]:
        questions = {}
        choose = {}
        num_words = {"one": 1, "two": 2, "three": 3, "four": 4}
        sub_pattern = re.compile(
            r"(?:Q\d{1,2}\s*)?\(([a-e])\)\s*[\.\)]?\s*(.*?)\[\s*(\d{1,3})\s*(?:marks?)?\s*\]",
            re.IGNORECASE | re.DOTALL
        )
        main_pattern = re.compile(
            r"Q(?:uestion)?\.?\s*(\d{1,2})\s*[\.\):\-]\s*(.*?)\[\s*(\d{1,3})\s*(?:marks?)?\s*\]",
            re.IGNORECASE | re.DOTALL
        )
        lines = text.split('\n')
        current_qnum = "1"
        for line in lines:
            q_match = re.match(r"Q(?:uestion)?\.?\s*(\d{1,2})\s*[\.\):\-]", line, re.IGNORECASE)
            if q_match:
                current_qnum = q_match.group(1)
            c = re.search(r"answer\s+any\s+(one|two|three|four|\d)", line, re.IGNORECASE)
            if c:
                w = c.group(1).lower()
                choose[current_qnum] = num_words.get(w) or int(w)
            sub_match = sub_pattern.search(line)
            if sub_match:
                sub_letter = sub_match.group(1)
                sub_text = sub_match.group(2).strip()
                sub_marks = int(sub_match.group(3))
                qid = f"{current_qnum}{sub_letter}"
                questions[qid] = {"text": sub_text, "marks": sub_marks}
        # Main questions (Q3, Q4, Q8...) that are not split into sub-questions
        for m in main_pattern.finditer(text):
            qnum = m.group(1)
            if any(re.fullmatch(rf"{qnum}[a-z]", k) for k in questions):
                continue
            qtext = m.group(2).strip()
            if len(qtext) > 20:
                questions[qnum] = {"text": qtext, "marks": int(m.group(3))}
        # "Answer any N": tag sub-questions so only the best N are counted
        for qid, q in questions.items():
            g = re.match(r"\d+", qid).group()
            if qid != g and g in choose:
                q["group"], q["choose"] = g, choose[g]
        return dict(sorted(questions.items(),
                           key=lambda kv: (int(re.match(r"\d+", kv[0]).group()), kv[0])))

    def parse_answer_key(self, text: str) -> Dict[str, Dict]:
        pattern = re.compile(
            r"Answer\s*(\d{1,2})(?:\s*\(([a-z])\))?\s*[:\-]\s*(.*?)(?=\n\s*Answer\s*\d|\Z)",
            re.IGNORECASE | re.DOTALL
        )
        key = {}
        matches = list(pattern.finditer(text))
        for m in matches:
            qnum = m.group(1)
            sub = m.group(2)
            qid = f"{qnum}{sub}" if sub else qnum
            body = m.group(3).strip()
            key_points = [
                ln.strip(" -*•\t\r")
                for ln in body.split("\n")
                if ln.strip() and len(ln.strip()) > 5
            ]
            key[qid] = {
                "model_answer": body,
                "key_points": key_points if key_points else [body]
            }
        return key

    # ---------- Scoring components ----------
    def _semantic_similarity(self, student_ans: str, model_ans: str) -> float:
        if not student_ans.strip() or not model_ans.strip():
            return 0.0
        emb = self.model.encode([student_ans, model_ans], convert_to_tensor=True)
        sim = util.cos_sim(emb[0], emb[1]).item()
        return max(0.0, min(1.0, sim))

    @staticmethod
    def _scale(x: float, lo: float, hi: float) -> float:
        return max(0.0, min(1.0, (x - lo) / (hi - lo)))

    @staticmethod
    def _tokens(text: str) -> List[str]:
        return re.findall(r"[a-z0-9']+", text.lower())

    def _content_words(self, text: str) -> set:
        return {w[:5] for w in self._tokens(text) if w not in self._STOP and len(w) > 2}

    def _lex_recall(self, student_ans: str, point: str) -> float:
        p = self._content_words(point)
        return len(p & self._content_words(student_ans)) / len(p) if p else 0.0

    def _clauses(self, key_points: List[str]) -> List[str]:
        """A one-line key is split into clauses so coverage is graded, not all-or-nothing."""
        if len(key_points) != 1:
            return key_points
        parts = re.split(r"[;,.:]|\s[-\u2013]\s|\s\+\s|\sand\s", key_points[0])
        parts = [x.strip() for x in parts if len(self._content_words(x)) >= 2]
        return parts if len(parts) > 1 else key_points

    def _key_point_scores(self, student_ans: str, key_points: List[str]) -> List[float]:
        """Per-key-point coverage (0..1): 40% meaning match, 60% word overlap."""
        if not key_points or not student_ans.strip():
            return [0.0]
        pts = self._clauses(key_points)
        chunks = [c.strip() for c in re.split(r"[.!?;\n]+", student_ans) if len(c.split()) >= 2] + [student_ans]
        sims = util.cos_sim(self.model.encode(pts, convert_to_tensor=True),
                            self.model.encode(chunks, convert_to_tensor=True)).tolist()
        return [0.4 * self._scale(max(row), 0.25, 0.60)
                + 0.6 * min(1.0, self._lex_recall(student_ans, pt) / 0.75)
                for pt, row in zip(pts, sims)]

    def _key_point_coverage(self, student_ans: str, key_points: List[str]) -> float:
        sc = self._key_point_scores(student_ans, key_points)
        return sum(sc) / len(sc)

    @staticmethod
    def _norm_exact(text: str) -> List[str]:
        t = text.lower().replace("can't", "cannot").replace("can not", "cannot").replace("n't", " not")
        return re.findall(r"[a-z0-9]+", t)

    def _exact_match(self, student_ans: str, model_ans: str) -> float:
        """Strict match for factual / grammar-transformation answers (aabb, Personification, ...)."""
        s, m = self._norm_exact(student_ans), self._norm_exact(model_ans)
        if not s or not m:
            return 0.0
        if len(m) == 1:
            r = max(difflib.SequenceMatcher(None, w, m[0]).ratio() for w in s)
        else:
            r = difflib.SequenceMatcher(None, s, m).ratio()
        return self._scale(r, 0.5, 1.0) ** 2

    def _expected_words(self, marks: int, model_words: int = 0) -> float:
        expected = marks * 15
        if model_words:
            expected = min(expected, max(8, model_words * self.LEN_MULT))
        return expected

    def _length_appropriateness(self, student_ans: str, marks: int, model_words: int = 0) -> float:
        ratio = len(student_ans.split()) / self._expected_words(marks, model_words)
        if ratio < 0.3:
            return 0.1 + 0.2 * ratio / 0.3
        if ratio < 0.6:
            return 0.3 + 0.3 * (ratio - 0.3) / 0.3
        if ratio <= 1.6:
            return 0.8 + 0.2 * min(1.0, (ratio - 0.6) / 0.4)
        return max(0.7, 1.6 / ratio)

    def _vocab_score(self, text: str) -> float:
        ws = [w for w in self._tokens(text) if w.isalpha()]
        if len(ws) < 3:
            return 0.0
        return self._scale(sum(map(len, ws)) / len(ws), 3.5, 5.0)

    _GRAMMAR_ERRORS = re.compile(
        r"\b(he|she|it|man|boy|girl|teacher|peddler|poet)\s+(feel|want|go|do|have|study|learn|say|become|steal|help|cause|"
        r"fight|use|know|think|take|get|change)\b"
        r"|\b(they|we|you|people|students|children)\s+(is|was)\b"
        r"|\b(he|she|they|we|i|you|who)\s+not\s+\w+"
        r"|\b(dont|doesnt|cant|wont|didnt|isnt)\b|(?<![\w'])i\s(?=[a-z])", re.IGNORECASE)

    def _heuristic_grammar(self, text: str) -> float:
        """LanguageTool fallback: capitalisation, punctuation, sentence length, common errors."""
        sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text) if x.strip()]
        if not sents:
            return 0.0
        # ignore address / salutation / signature lines in letters and notices
        sents = [x for x in sents if len(x.split()) >= 5] or sents
        n, words = len(sents), sum(len(x.split()) for x in sents)
        cap = sum(1 for x in sents if x[0].isupper() or not x[0].isalpha()) / n
        punct = sum(1 for x in sents if x[-1] in ".!?\"')") / n
        avg = words / n
        length_ok = 1.0 if 6 <= avg <= 35 else (avg / 6 if avg < 6 else max(0.5, 35 / avg))
        errors = len(self._GRAMMAR_ERRORS.findall(text))
        score = 0.97 * (0.3 * cap + 0.3 * punct + 0.4 * length_ok) - min(0.4, 0.12 * errors)
        if words < 3:
            score = min(score, 0.3)
        elif words < 6:
            score = min(score, 0.5)
        return max(0.05, min(1.0, score))

    def _grammar_score(self, student_ans: str) -> float:
        if not student_ans.strip():
            return 0.0
        if not self.grammar_tool:
            return self._heuristic_grammar(student_ans)
        try:
            matches = self.grammar_tool.check(student_ans)
            words = max(1, len(student_ans.split()))
            error_rate = len(matches) / words
            return max(0.0, 1.0 - min(error_rate * 4, 1.0))
        except Exception:
            return self._heuristic_grammar(student_ans)

    # ---------- Format-aware scoring (letters / notices) ----------
    _DATE = re.compile(
        r"\b\d{1,2}(?:st|nd|rd|th)?[\s/\-.]+(?:\d{1,2}|[a-z]{3,9})[\s/\-.,]+\d{2,4}\b"
        r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}\b",
        re.IGNORECASE)

    @staticmethod
    def _question_kind(qid: str, qtext: str) -> str:
        t = qtext.lower()
        if qid.isdigit():
            if re.search(r"\bletter\b", t):
                return "letter"
            if re.search(r"\bnotice\b", t):
                return "notice"
        if re.search(r"\btitle\b", t):
            return "title"
        if re.search(r"indirect speech|passive|rewrite|correct the|rhyme scheme|figure of speech|\ba word\b|synonym|antonym", t):
            return "exact"
        return ""

    @staticmethod
    def _extract_segment(text: str, qnum: str) -> str:
        m = re.search(
            rf"Q(?:uestion)?\.?\s*{qnum}\s*[\.\):\-](.*?)(?=Q(?:uestion)?\.?\s*\d{{1,2}}\s*[\.\):\-]|\Z)",
            text, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    def _format_score(self, text: str, kind: str) -> float:
        """Fraction (0-1) of expected format elements present in a letter/notice."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            return 0.0
        low = [l.lower() for l in lines]
        joined = " ".join(low)

        def first(pred):
            return next((i for i, l in enumerate(low) if pred(l)), None)

        if kind == "letter":
            date_i = first(self._DATE.search)
            recv_i = first(lambda l: re.search(r"\beditor\b|\bnewspaper\b|\bdaily\b", l)
                           and not l.startswith(("sub", "dear")))
            subj_i = first(lambda l: re.match(r"(sub|subject|re)\s*[:\-]", l))
            sal_i = first(lambda l: re.match(r"(dear\s+)?(sir|madam)\b", l))
            close_i = first(lambda l: re.search(r"yours\s+(faithfully|truly|sincerely)", l))
            marks = [i for i in (date_i, recv_i, subj_i, sal_i) if i is not None]
            sender = 1.0 if marks and min(marks) >= 1 else 0.0
            start = (sal_i if sal_i is not None else subj_i if subj_i is not None else -1) + 1
            body = " ".join(lines[start:close_i]) if close_i is not None else " ".join(lines[start:])
            body_s = 0.5 * (len(body.split()) >= 40) + 0.5 * bool(
                re.search(r"\b(should|must|urge|request|suggest|measures|steps|ban|strict|awareness)\b", body.lower()))
            closing = 0.0 if close_i is None else (1.0 if close_i < len(lines) - 1 else 0.5)
            parts = [sender, date_i is not None, recv_i is not None, subj_i is not None,
                     sal_i is not None, body_s, closing]
        elif kind == "notice":
            top = lines[:4]
            org = re.compile(r"\b(school|vidyalaya|college|academy|institute|club|society)\b", re.I)
            hdr = [l for l in lines[:6] if len(l.split()) <= 12 and not l.endswith(".")]
            title = any(not (re.fullmatch(r"\W*notice\W*", l.lower()) or org.search(l)
                             or self._DATE.search(l.lower())) for l in hdr)
            body_s = sum(bool(re.search(p, joined)) for p in (
                r"\b(competition|event|meeting|programme|program|drive|workshop|camp|will be|organi[sz]ed|conducted|held)\b",
                self._DATE.pattern + r"|\b\d{1,2}[:.]\d{2}\b|\b\d{1,2}\s*(a\.?m|p\.?m)\b|\b(mon|tues|wednes|thurs|fri|satur|sun)day\b",
                r"\b(venue|hall|auditorium|ground|room|library|lab|campus|playground)\b",
                r"\b(all|students|class|classes|members|interested|parents|teachers)\b")) / 4
            sign = bool(re.search(r"\bhead\s*(boy|girl)\b|\bsecretary\b|\bcaptain\b|\bprincipal\b",
                                  " ".join(low[-3:])))
            parts = [bool(re.search(r"\bnotice\b", " ".join(low[:3]))),
                     any(org.search(l) for l in top), bool(self._DATE.search(joined)),
                     title, body_s, sign]
        else:
            return 0.0
        return sum(float(p) for p in parts) / len(parts)

    # ---------- Per-question evaluation ----------
    def evaluate_answer(self, student_ans: str, key_entry: Dict, marks: int, kind: str = "") -> Dict:
        student_ans = (student_ans or "").strip()
        model = key_entry.get("model_answer", "").strip()
        open_ended = model.lower().startswith("any ")
        quoted = re.findall(r'"([^"]+)"', model)
        if open_ended and quoted:
            model = quoted[0]
        mw = len(model.split())
        fmt_kind = kind in ("letter", "notice")
        exact = kind == "exact" or 0 < mw <= 3
        fmt = None
        bonus_ok = False
        all_kp = False

        if not student_ans or not model:
            content = organization = language = grammar = final_pct = 0.0
        else:
            raw = self._semantic_similarity(student_ans, model)
            if exact:
                content = self._exact_match(student_ans, model)
            elif open_ended:
                content = 0.6 * self._scale(raw, 0.2, 0.6) + 0.4 * self._lex_recall(student_ans, model)
            elif fmt_kind:
                content = self._scale(raw, 0.10, 0.45)
            else:
                # content = 30% semantic + 70% key-point coverage
                sem = self._scale(raw, self.SEM_LOW, self.SEM_HIGH)
                kps = self._key_point_scores(student_ans, key_entry.get("key_points") or [model])
                kp = sum(kps) / len(kps)
                content = 0.3 * sem + 0.7 * kp
                # reward strong answers: high semantic + coverage -> 0.9+, else a smooth lift above kp 0.5
                if sem > 0.7 and kp > 0.7:
                    content = max(content, 0.9)
                else:
                    content = min(1.0, content + 0.3 * max(0.0, (kp - 0.5) / 0.5))
                all_kp = min(kps) >= 0.7
                bonus_ok = kp >= 0.5
            if exact or open_ended:
                # short factual answers: judged on correctness alone
                final_pct = organization = language = grammar = content
            else:
                organization = 1.0 if kind == "title" else self._length_appropriateness(student_ans, marks, 0 if fmt_kind else mw)
                language = 0.5 * content + 0.5 * self._vocab_score(student_ans)
                grammar = self._grammar_score(student_ans)
                final_pct = (
                    content * self.weights["content"]
                    + organization * self.weights["organization"]
                    + language * self.weights["language"]
                    + grammar * self.weights["grammar"]
                )
                if fmt_kind:
                    fmt = self._format_score(student_ans, kind)
                    final_pct = 0.6 * fmt + 0.4 * final_pct
                # bonuses: covers every key point (+15%), comprehensive length (+10%)
                if bonus_ok and not fmt_kind:
                    wc = len(student_ans.split())
                    if all_kp:
                        final_pct += 0.15
                    if 0.8 <= wc / self._expected_words(marks, mw) <= 2.0:
                        final_pct += 0.10
                    final_pct = min(1.0, final_pct)
                # completeness penalty (key answers are terse, so use at least marks*8 words)
                ratio = len(student_ans.split()) / max(mw, marks * 8)
                if ratio < 0.10:
                    final_pct = min(final_pct, 0.20)
                elif ratio < 0.20:
                    final_pct = min(final_pct, 0.40)

        result = {
            "marks_awarded": round(final_pct * marks, 1),
            "max_marks": marks,
            "content_score": round(content * 100, 1),
            "organization_score": round(organization * 100, 1),
            "language_score": round(language * 100, 1),
            "grammar_score": round(grammar * 100, 1),
        }
        if fmt is not None:
            result["format_score"] = round(fmt * 100, 1)
        return result

    # ---------- Full student evaluation ----------
    def evaluate_student(self, student_answers: Dict[str, str],
                          questions: Dict[str, Dict],
                          answer_key: Dict[str, Dict]) -> Dict:
        results = {}

        if "full_text" in student_answers and len(student_answers) == 1:
            full_text = student_answers["full_text"].lower()
            full_words = set(full_text.split())

            for qnum, qinfo in questions.items():
                marks = qinfo["marks"]
                qtext = qinfo["text"].lower()

                stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'of', 'for', 'is', 'are', 'was', 'were', 'what', 'how', 'why', 'explain', 'describe', 'discuss', 'write', 'note', 'short', 'and', 'or', 'but', 'if', 'then', 'that', 'this', 'with', 'from', 'has', 'have', 'had', 'do', 'does', 'did', 'can', 'could', 'will', 'would', 'should', 'may', 'might', 'must', 'shall', 'not', 'its', 'your', 'you', 'we', 'they', 'he', 'she', 'it', 'me', 'us', 'him', 'her', 'them', 'my', 'our', 'his', 'their'}
                q_keywords = {w for w in qtext.split() if len(w) > 2 and w not in stop_words}

                matched_words = []
                for kw in q_keywords:
                    # Only use keywords that are at least 4 characters
                    if len(kw) < 3:
                        continue
                    kw_clean = kw.strip("?.'\"!()")
                    for fw in full_words:
                        if len(fw) < 2:
                            continue
                        # Match if: keyword starts with OCR word, or OCR word starts with keyword
                        # or they share a 3+ char substring
                        if  (len(kw_clean) >= 3 and len(fw) >= 3 and (kw_clean[:3] in fw or fw[:3] in kw_clean or kw_clean in fw or fw in kw_clean)):
                            matched_words.append(fw)

                relevant_chunks = []
                if matched_words:
                    sentences = re.split(r'[.!?~]+', full_text)
                    for sentence in sentences:
                        for mw in matched_words:
                            if mw in sentence:
                                relevant_chunks.append(sentence)
                                break

                student_ans = " ".join(relevant_chunks[:3]) if relevant_chunks else ""
                kind = self._question_kind(qnum, qinfo["text"])
                if kind in ("letter", "notice"):
                    student_ans = self._extract_segment(student_answers["full_text"], qnum) or student_ans

                if qnum in ['1b', '5a', '6a']:
                    print(f"Q{qnum}: keywords={list(q_keywords)[:5]}, matched={matched_words[:5]}, chunks={len(relevant_chunks)}")

                key_entry = answer_key.get(qnum, {"model_answer": "", "key_points": []})
                q_result = self.evaluate_answer(student_ans, key_entry, marks, kind)
                results[qnum] = q_result
        else:
            for qnum, qinfo in questions.items():
                marks = qinfo["marks"]
                student_ans = student_answers.get(qnum, "")
                key_entry = answer_key.get(qnum, {"model_answer": "", "key_points": []})
                q_result = self.evaluate_answer(student_ans, key_entry, marks,
                                                self._question_kind(qnum, qinfo["text"]))
                results[qnum] = q_result

        # "Answer any N": count only the best N sub-questions of each group
        groups = {q["group"]: q["choose"] for q in questions.values() if q.get("choose")}
        for g, n in groups.items():
            subs = sorted((k for k, q in questions.items() if q.get("group") == g),
                          key=lambda k: results[k]["marks_awarded"], reverse=True)
            for k in subs[n:]:
                results[k]["counted"] = False
        counted = [r for r in results.values() if r.get("counted", True)]
        total_awarded = sum(r["marks_awarded"] for r in counted)
        total_max = sum(r["max_marks"] for r in counted)

        percentage = round((total_awarded / total_max) * 100, 2) if total_max else 0.0
        return {
            "question_results": results,
            "total_marks_awarded": round(total_awarded, 1),
            "total_max_marks": total_max,
            "percentage": percentage,
            "grade": self.compute_grade(percentage),
        }

    @staticmethod
    def compute_grade(percentage: float) -> str:
        if percentage >= 91:
            return "A1"
        if percentage >= 81:
            return "A2"
        if percentage >= 71:
            return "B1"
        if percentage >= 61:
            return "B2"
        if percentage >= 51:
            return "C1"
        if percentage >= 41:
            return "C2"
        if percentage >= 33:
            return "D"
        return "E"