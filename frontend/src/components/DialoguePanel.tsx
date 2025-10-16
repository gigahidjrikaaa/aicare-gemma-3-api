import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { useClientConfig } from "../context/ConfigContext";
import { apiFetch, apiFetchStream } from "../lib/apiClient";
import { useToast } from "./Toast";

type DialogueResponse = {
  transcript: string;
  assistant_text: string;
  audio_base64?: string;
  metadata?: Record<string, unknown>;
};

type StreamEvent = {
  event: string;
  data: unknown;
};

const defaultRequest = {
  instructions: "You are a helpful clinical assistant.",
  stream_audio: true
};

export function DialoguePanel() {
  const { config } = useClientConfig();
  const { push } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [request, setRequest] = useState(defaultRequest);
  const [result, setResult] = useState<DialogueResponse | null>(null);
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

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      push({ title: "Upload audio to start", variant: "error" });
      return;
    }
    const form = new FormData();
    form.append("audio", file);
    form.append("instructions", request.instructions);
    form.append("stream_audio", String(request.stream_audio));
    try {
      const { data } = await apiFetch<DialogueResponse>(config, "/v1/dialogue", {
        method: "POST",
        body: form,
        parseJson: true
      });
      setResult(data);
      if (data.audio_base64) {
        const blob = base64ToBlob(data.audio_base64);
        if (objectUrl) {
          URL.revokeObjectURL(objectUrl);
        }
        const url = URL.createObjectURL(blob);
        setObjectUrl(url);
        setAudioUrl(url);
      }
      push({ title: "Dialogue completed" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      push({ title: "Dialogue failed", description: message, variant: "error" });
    }
  };

  const handleStream = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      push({ title: "Upload audio to start", variant: "error" });
      return;
    }
    setStreamLog([]);
    setResult(null);
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      setObjectUrl(null);
    }
    setAudioUrl(null);
    const form = new FormData();
    form.append("audio", file);
    form.append("instructions", request.instructions);
    form.append("stream_audio", "true");
    const audioChunks: ArrayBuffer[] = [];
    try {
      await apiFetchStream(
        config,
        "/v1/dialogue",
        {
          method: "POST",
          body: form
        },
        (event) => {
          setStreamLog((prev) => [...prev, { event: String(event.event ?? "data"), data: event.data }]);
          if (event.event === "transcript" && typeof event.data === "string") {
            const transcript = event.data as string;
            setResult((prev) => ({ ...(prev ?? { transcript: "", assistant_text: "" }), transcript }));
          }
          if (event.event === "assistant_text" && typeof event.data === "string") {
            const assistant = event.data as string;
            setResult((prev) => ({ ...(prev ?? { transcript: "", assistant_text: "" }), assistant_text: assistant }));
          }
          if (event.event === "audio_chunk" && typeof event.data === "string") {
            const chunk = Uint8Array.from(atob(event.data), (c) => c.charCodeAt(0)).buffer;
            audioChunks.push(chunk);
          }
        }
      );
      if (audioChunks.length) {
        const blob = new Blob(audioChunks, { type: "audio/wav" });
        const url = URL.createObjectURL(blob);
        if (objectUrl) {
          URL.revokeObjectURL(objectUrl);
        }
        setObjectUrl(url);
        setAudioUrl(url);
      }
      push({ title: "Streaming dialogue finished" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown streaming error";
      push({ title: "Streaming failed", description: message, variant: "error" });
    }
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files?.length) {
      setResult(null);
      setAudioUrl(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-2 md:col-span-2">
          <span className="text-sm font-medium">User audio</span>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            onChange={handleFileChange}
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
        </label>
        <label className="flex h-full flex-col gap-2 md:col-span-2">
          <span className="text-sm font-medium">Instructions</span>
          <textarea
            className="h-32 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            value={request.instructions}
            onChange={(event) => setRequest((prev) => ({ ...prev, instructions: event.target.value }))}
          />
        </label>
        <div className="flex items-center gap-2 md:col-span-2">
          <button type="submit" className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950">
            Run dialogue
          </button>
          <button
            type="button"
            onClick={handleStream}
            className="rounded-md border border-emerald-400 px-4 py-2 text-sm font-semibold text-emerald-300"
          >
            Stream dialogue
          </button>
        </div>
      </form>
      {result ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="text-sm font-semibold text-emerald-300">Results</h3>
          <p className="mt-2 text-xs uppercase tracking-wide text-slate-400">Transcript</p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{result.transcript}</p>
          <p className="mt-4 text-xs uppercase tracking-wide text-slate-400">Assistant response</p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{result.assistant_text}</p>
        </div>
      ) : null}
      {audioUrl ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="text-sm font-semibold text-emerald-300">Assistant audio</h3>
          <audio controls className="mt-2 w-full" src={audioUrl} />
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

function base64ToBlob(base64: string) {
  const binary = atob(base64);
  const array = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    array[i] = binary.charCodeAt(i);
  }
  return new Blob([array], { type: "audio/wav" });
}

