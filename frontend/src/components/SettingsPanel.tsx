import { FormEvent, useEffect, useState } from "react";
import { useClientConfig } from "../context/ConfigContext";

export function SettingsPanel() {
  const { config, updateConfig } = useClientConfig();
  const [draft, setDraft] = useState(config);

  useEffect(() => {
    setDraft(config);
  }, [config]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    updateConfig(draft);
  };

  return (
    <details className="rounded-md border border-slate-800 bg-slate-900/60 p-4">
      <summary className="cursor-pointer text-sm font-medium text-emerald-400">Connection settings</summary>
      <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3 text-sm">
        <label className="flex flex-col gap-1">
          <span className="font-medium">API base URL</span>
          <input
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
            value={draft.baseUrl}
            onChange={(event) => setDraft((prev) => ({ ...prev, baseUrl: event.target.value }))}
            placeholder="http://localhost:8000"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-medium">API key (optional)</span>
          <input
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
            value={draft.apiKey}
            onChange={(event) => setDraft((prev) => ({ ...prev, apiKey: event.target.value }))}
            placeholder="sk-..."
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-medium">Preferred streaming mode</span>
          <select
            className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
            value={draft.streamingMode}
            onChange={(event) =>
              setDraft((prev) => ({ ...prev, streamingMode: event.target.value as typeof draft.streamingMode }))
            }
          >
            <option value="rest">REST (HTTP streaming)</option>
            <option value="websocket">WebSocket</option>
          </select>
        </label>
        <div className="flex items-center gap-2">
          <button type="submit" className="rounded-md bg-emerald-500 px-3 py-2 font-semibold text-slate-950">
            Save
          </button>
          <p className="text-xs text-slate-400">Settings persist in your browser only.</p>
        </div>
      </form>
    </details>
  );
}
