import { FormEvent, useEffect, useMemo, useState } from "react";
import { useClientConfig } from "../context/ConfigContext";
import { apiFetch, apiFetchStream } from "../lib/apiClient";
import { useToast } from "./Toast";

type SpeechResponse = {
  audio_base64?: string;
  format?: string;
  metadata?: Record<string, unknown>;
};

type StreamEvent = {
  event: string;
  data: unknown;
};

const defaultRequest = {
  text: "Thanks for testing the Higgs Audio integration!",
  voice: "alloy",
  model: "higgs-audio-v2",
  response_format: "wav",
  sample_rate: 44100,
  speed: 1,
  stream: false
};

export function SynthesisPanel() {
  const { config } = useClientConfig();
  const { push } = useToast();
  const [request, setRequest] = useState(defaultRequest);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [streamLog, setStreamLog] = useState<StreamEvent[]>([]);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [objectUrl]);

  const headers = useMemo(() => ({ "Content-Type": "application/json" }), []);

  const runSynthesis = async (event: FormEvent) => {
    event.preventDefault();
    setStreamLog([]);
    try {
      const { data } = await apiFetch<SpeechResponse>(config, "/v1/text-to-speech", {
        method: "POST",
        headers,
        body: JSON.stringify({ ...request, stream: false })
      });
      if (data.audio_base64) {
        const blob = base64ToBlob(data.audio_base64, request.response_format ?? "audio/wav");
        const url = URL.createObjectURL(blob);
        if (objectUrl) {
          URL.revokeObjectURL(objectUrl);
        }
        setObjectUrl(url);
        setAudioUrl(url);
      }
      push({ title: "Synthesis complete" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      push({ title: "Synthesis failed", description: message, variant: "error" });
    }
  };

  const runStreaming = async () => {
    setStreamLog([]);
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      setObjectUrl(null);
    }
    setAudioUrl(null);
    const chunks: ArrayBuffer[] = [];
    try {
      await apiFetchStream(
        config,
        "/v1/text-to-speech",
        {
          method: "POST",
          headers,
          body: JSON.stringify({ ...request, stream: true })
        },
        (event) => {
          setStreamLog((prev) => [...prev, { event: String(event.event ?? "data"), data: event.data }]);
          if (event.event === "audio_chunk" && typeof event.data === "string") {
            const chunk = Uint8Array.from(atob(event.data), (c) => c.charCodeAt(0)).buffer;
            chunks.push(chunk);
          }
        }
      );
      if (chunks.length) {
        const blob = new Blob(chunks, { type: `audio/${request.response_format ?? "wav"}` });
        const url = URL.createObjectURL(blob);
        if (objectUrl) {
          URL.revokeObjectURL(objectUrl);
        }
        setObjectUrl(url);
        setAudioUrl(url);
      }
      push({ title: "Streaming synthesis finished" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown streaming error";
      push({ title: "Streaming failed", description: message, variant: "error" });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={runSynthesis} className="grid gap-4 md:grid-cols-2">
        <label className="flex h-full flex-col gap-2 md:col-span-2">
          <span className="text-sm font-medium">Text</span>
          <textarea
            className="h-32 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={request.text}
            onChange={(event) => setRequest((prev) => ({ ...prev, text: event.target.value }))}
          />
        </label>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Voice</label>
          <input
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={request.voice}
            onChange={(event) => setRequest((prev) => ({ ...prev, voice: event.target.value }))}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Model</label>
          <input
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={request.model}
            onChange={(event) => setRequest((prev) => ({ ...prev, model: event.target.value }))}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Response format</label>
          <select
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={request.response_format}
            onChange={(event) => setRequest((prev) => ({ ...prev, response_format: event.target.value }))}
          >
            <option value="wav">WAV</option>
            <option value="mp3">MP3</option>
            <option value="ogg">OGG</option>
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Sample rate</label>
          <input
            type="number"
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={request.sample_rate}
            onChange={(event) => setRequest((prev) => ({ ...prev, sample_rate: Number(event.target.value) }))}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-wide text-slate-400">Speed</label>
          <input
            type="number"
            step="0.1"
            min="0.5"
            max="2"
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={request.speed}
            onChange={(event) => setRequest((prev) => ({ ...prev, speed: Number(event.target.value) }))}
          />
        </div>
        <div className="flex items-center gap-2 md:col-span-2">
          <button type="submit" className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950">
            Render audio
          </button>
          <button
            type="button"
            onClick={runStreaming}
            className="rounded-md border border-emerald-400 px-4 py-2 text-sm font-semibold text-emerald-300"
          >
            Stream audio
          </button>
        </div>
      </form>
      {audioUrl ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="text-sm font-semibold text-emerald-300">Preview</h3>
          <audio controls className="mt-2 w-full" src={audioUrl} />
          <a
            className="mt-3 inline-flex items-center text-xs text-emerald-300 underline"
            href={audioUrl}
            download="speech-output"
          >
            Download audio
          </a>
        </div>
      ) : null}
      {streamLog.length ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="text-sm font-semibold text-emerald-300">Streaming events</h3>
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

function base64ToBlob(base64: string, format: string) {
  const binary = atob(base64);
  const array = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    array[i] = binary.charCodeAt(i);
  }
  return new Blob([array], { type: `audio/${format}` });
}
