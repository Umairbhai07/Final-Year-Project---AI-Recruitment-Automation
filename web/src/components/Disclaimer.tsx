import { useAiMock } from "../lib/aiMode";

/** Shown only while the backend runs without an AI key, so simulated scores are never mistaken for real ones. */
export function Disclaimer() {
  const mock = useAiMock();
  if (!mock) return null;
  return (
    <div className="mb-6 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600" role="note">
      <b className="font-semibold text-slate-900">Demo AI mode.</b> No AI key is set, so scores and transcripts are simulated.
      Add <code>LLM_API_KEY</code> in <code>backend/.env</code> and set <code>AI_MOCK=false</code> to use real AI.
    </div>
  );
}
