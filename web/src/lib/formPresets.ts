import type { FormQuestion } from "../api/types";

/** Ready-made questions a recruiter can add with one click. Same ids as the backend's default form. */
export const PRESET_QUESTIONS: FormQuestion[] = [
  { id: "total_experience", label: "Total years of work experience", type: "number", required: true, min: 0, max: 50,
    help: "Include internships and part-time work. Enter 0 if you are a fresh graduate." },
  { id: "highest_degree", label: "Highest degree", type: "select", required: true,
    options: ["Matric / O-Levels", "Intermediate / A-Levels", "Diploma", "Bachelor's", "Master's", "PhD"] },
  { id: "field_of_study", label: "Field of study", type: "text", required: false },
  { id: "cgpa", label: "Latest CGPA or grade", type: "text", required: true, help: "For example 3.4 / 4.0, 78%, or A grade." },
  { id: "graduation_year", label: "Graduation year", type: "number", required: false, min: 1970, max: 2035 },
  { id: "university", label: "University / institute", type: "text", required: false },
  { id: "current_title", label: "Current or most recent job title", type: "text", required: false },
  { id: "notice_period", label: "When can you join?", type: "select", required: false,
    options: ["Immediately", "Within 2 weeks", "Within 1 month", "More than 1 month"] },
  { id: "expected_salary", label: "Expected monthly salary (PKR)", type: "number", required: false, min: 0 },
  { id: "portfolio", label: "LinkedIn, GitHub or portfolio link", type: "url", required: false },
  { id: "onsite", label: "Can you work on-site at our office?", type: "yes_no", required: false },
];

export const DEFAULT_FORM_IDS = ["total_experience", "highest_degree", "field_of_study", "cgpa", "graduation_year"];

export const DEFAULT_FORM: FormQuestion[] = []; // degree, experience and CGPA now come from the candidate profile

export const TYPE_LABEL: Record<FormQuestion["type"], string> = {
  text: "Short answer",
  long_text: "Paragraph",
  number: "Number",
  select: "Dropdown",
  yes_no: "Yes / No",
  url: "Link",
};
