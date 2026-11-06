import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { API_URL } from "../api/client";

/** True when the backend has no AI key (or AI_MOCK=true): scores and transcripts are simulated. */
export function useAiMock() {
  const { data } = useQuery({
    queryKey: ["health"],
    queryFn: async () => (await axios.get<{ status: string; ai_mock?: boolean }>(`${API_URL}/health`)).data,
    staleTime: 60_000,
  });
  return !!data?.ai_mock;
}
