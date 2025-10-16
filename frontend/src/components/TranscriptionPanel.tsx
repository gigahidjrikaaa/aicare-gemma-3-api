import { ChangeEvent, FormEvent, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useClientConfig } from "../context/ConfigContext";
import { apiFetch, type ApiError } from "../lib/apiClient";
import { useToast } from "./Toast";

type TranscriptSegment = {
  start: number;
  end: number;
  text: string;
};

type TranscriptionResponse = {
  text: string;
  language?: string;
  segments?: TranscriptSegment[];
  metadata?: Record<string, unknown>;
};

const defaultOptions = {
  model: "whisper-large-v3",
  responseFormat: "verbose_json",
  temperature: 0
};

export function TranscriptionPanel() {
  const { config } = useClientConfig();
  const { push } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [options, setOptions] = useState(defaultOptions);
  const [result, setResult] = useState<TranscriptionResponse | null>(null);

  const mutation = useMutation<TranscriptionResponse, ApiError, FormData>({
    mutationFn: async (formData) => {
      const { data, requestId } = await apiFetch<TranscriptionResponse>(config, "/v1/speech-to-text", {
        method: "POST",
        body: formData
      });
      push({ title: "Transcription ready", description: requestId ? `Request ID: ${requestId}` : undefined });
      return data;
    },
    onSuccess: (data) => setResult(data),
    onError: (error) => push({ title: `Transcription failed (${error.status})`, description: error.message, variant: "error" })
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      push({ title: "Select an audio file first", variant: "error" });
      return;
    }
    const form = new FormData();
    form.append("file", file);
    form.append("model", options.model);
    form.append("response_format", options.responseFormat);
    form.append("temperature", String(options.temperature));
    mutation.mutate(form);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files?.length) {
      setResult(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-2 md:col-span-2">
          <span className="text-sm font-medium">Audio file</span>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            onChange={handleFileChange}
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
        </label>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Model</label>
          <input
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={options.model}
            onChange={(event) => setOptions((prev) => ({ ...prev, model: event.target.value }))}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Response format</label>
          <select
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={options.responseFormat}
            onChange={(event) => setOptions((prev) => ({ ...prev, responseFormat: event.target.value }))}
          >
            <option value="json">json</option>
            <option value="verbose_json">verbose_json</option>
            <option value="text">text</option>
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Temperature</label>
          <input
            type="number"
            step="0.1"
            min="0"
            max="1"
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={options.temperature}
            onChange={(event) => setOptions((prev) => ({ ...prev, temperature: Number(event.target.value) }))}
          />
        </div>
        <button
          type="submit"
          className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 md:col-span-2"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? "Uploading..." : "Transcribe"}
        </button>
      </form>
      {result ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="text-sm font-semibold text-emerald-300">Transcript</h3>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{result.text}</p>
          {result.segments?.length ? (
            <div className="mt-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Segments</h4>
              <ul className="mt-2 flex flex-col gap-2 text-xs">
                {result.segments.map((segment, index) => (
                  <li key={index} className="rounded bg-slate-800/60 p-2">
                    <span className="text-emerald-400">[{segment.start.toFixed(2)}s - {segment.end.toFixed(2)}s]</span> {segment.text}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
