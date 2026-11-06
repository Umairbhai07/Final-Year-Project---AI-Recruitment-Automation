import type { FormQuestion } from "../api/types";

export type Answers = Record<string, string>;

const URL_RE = /^https?:\/\/[^\s/$.?#].[^\s]*$/i;

/** Same rules as the server, so candidates see problems before uploading. Returns {questionId: message}. */
export function checkAnswers(questions: FormQuestion[], answers: Answers): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const q of questions) {
    const v = (answers[q.id] ?? "").trim();
    if (!v) {
      if (q.required) errors[q.id] = "This question is required.";
      continue;
    }
    if (q.type === "number") {
      const n = Number(v);
      if (Number.isNaN(n)) errors[q.id] = "Enter a number.";
      else if (q.min != null && n < q.min) errors[q.id] = `Must be at least ${q.min}.`;
      else if (q.max != null && n > q.max) errors[q.id] = `Must be at most ${q.max}.`;
    } else if (q.type === "url" && !URL_RE.test(v)) {
      errors[q.id] = "Enter a full link starting with https://";
    }
  }
  return errors;
}
