import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useClientConfig } from "../context/ConfigContext";
import { apiFetch, apiFetchStream, type ApiError } from "../lib/apiClient";
import { useToast } from "./Toast";

type GenerationResponse = {
  id: string;
  output: string;
  metadata?: Record<string, unknown>;
};

type StreamEvent = {
  event: string;
  data: unknown;
};

const defaultRequest = {
  prompt: "Hello!",
  maxOutputTokens: 256,
  temperature: 0.7,
  topP: 0.95,
  topK: 40
};

export function GenerationPanel() {
  const { config } = useClientConfig();
  const { push } = useToast();
  const [request, setRequest] = useState(defaultRequest);
  const [result, setResult] = useState<GenerationResponse | null>(null);
  const [streamLog, setStreamLog] = useState<StreamEvent[]>([]);

  const mutation = useMutation<GenerationResponse, ApiError, typeof request>({
    mutationFn: async (payload) => {
      const { data, requestId } = await apiFetch<GenerationResponse>(config, "/v1/generate", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      push({ title: "Generation complete", description: requestId ? `Request ID: ${requestId}` : undefined });
      return data;
    },
    onSuccess: (data) => {
      setResult(data);
    },
    onError: (error) => {
      push({ title: `Generation failed (${error.status})`, description: error.message, variant: "error" });
    }
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setStreamLog([]);
    mutation.mutate(request);
  };

  const handleStream = async () => {
    setStreamLog([]);
    setResult(null);
    try {
      await apiFetchStream(config, "/v1/generate_stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request)
      }, (event) => {
        setStreamLog((prev) => [...prev, { event: String(event.event ?? "data"), data: event.data }]);
        if (event.event === "final_output" && typeof event.data === "object" && event.data) {
          setResult({
            id: String((event.data as Record<string, unknown>).id ?? "stream"),
            output: String((event.data as Record<string, unknown>).output ?? ""),
            metadata: event.data as Record<string, unknown>
          });
        }
      });
      push({ title: "Streaming run finished" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown streaming error";
      push({ title: "Streaming failed", description: message, variant: "error" });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
        <label className="flex h-full flex-col gap-2 md:col-span-2">
          <span className="text-sm font-medium">Prompt</span>
          <textarea
            className="h-40 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={request.prompt}
            onChange={(event) => setRequest((prev) => ({ ...prev, prompt: event.target.value }))}
          />
        </label>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Temperature</label>
          <input
            type="number"
            step="0.1"
            min="0"
            max="2"
            value={request.temperature}
            onChange={(event) => setRequest((prev) => ({ ...prev, temperature: Number(event.target.value) }))}
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Top P</label>
          <input
            type="number"
            step="0.05"
            min="0"
            max="1"
            value={request.topP}
            onChange={(event) => setRequest((prev) => ({ ...prev, topP: Number(event.target.value) }))}
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Top K</label>
          <input
            type="number"
            min="1"
            max="256"
            value={request.topK}
            onChange={(event) => setRequest((prev) => ({ ...prev, topK: Number(event.target.value) }))}
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Max output tokens</label>
          <input
            type="number"
            min="1"
            max="2048"
            value={request.maxOutputTokens}
            onChange={(event) => setRequest((prev) => ({ ...prev, maxOutputTokens: Number(event.target.value) }))}
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex items-center gap-2 md:col-span-2">
          <button
            type="submit"
            className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "Running..." : "Run sync"}
          </button>
          <button
            type="button"
            onClick={handleStream}
            className="rounded-md border border-emerald-400 px-4 py-2 text-sm font-semibold text-emerald-300"
          >
            Run streaming
          </button>
          {mutation.isError ? (
            <span className="text-xs text-red-400">{mutation.error?.message}</span>
          ) : null}
        </div>
      </form>
      {result ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="text-sm font-semibold text-emerald-300">Result</h3>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{result.output}</p>
        </div>
      ) : null}
      {streamLog.length > 0 ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="text-sm font-semibold text-emerald-300">Stream events</h3>
          <ul className="mt-2 flex flex-col gap-2 text-xs">
            {streamLog.map((entry, index) => (
              <li key={index} className="rounded bg-slate-800/60 p-2 font-mono">
                <span className="text-emerald-400">{entry.event}:</span> {JSON.stringify(entry.data)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
