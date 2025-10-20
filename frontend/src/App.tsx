import { useMemo } from "react";
import { SettingsPanel } from "./components/SettingsPanel";
import { TabView } from "./components/TabView";
import { ConfigProvider } from "./context/ConfigContext";
import { TabsProvider, useTabs } from "./context/TabsContext";
import { DialoguePanel } from "./components/DialoguePanel";
import { GenerationPanel } from "./components/GenerationPanel";
import { SynthesisPanel } from "./components/SynthesisPanel";
import { TranscriptionPanel } from "./components/TranscriptionPanel";
import { ToastProvider } from "./components/Toast";

const tabs = [
  { id: "generate", label: "Text Generation", component: GenerationPanel },
  { id: "stt", label: "Speech to Text", component: TranscriptionPanel },
  { id: "tts", label: "Text to Speech", component: SynthesisPanel },
  { id: "dialogue", label: "Dialogue", component: DialoguePanel }
];

function AppShell() {
  const tabConfig = useMemo(() => tabs, []);
  const { activeTab, setActiveTab } = useTabs();
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6">
        <header className="flex flex-col gap-2 border-b border-slate-800 pb-4">
          <h1 className="text-2xl font-semibold">AICare Speech Playground</h1>
          <p className="text-sm text-slate-300">
            Exercise the LLM, Whisper transcription, OpenAudio synthesis, and the orchestrated dialogue pipeline using your
            deployment credentials.
          </p>
          <SettingsPanel />
        </header>
        <main className="flex flex-col gap-4">
          <TabView tabs={tabConfig} activeTab={activeTab} onTabChange={setActiveTab} />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <ConfigProvider>
        <TabsProvider defaultTab="generate">
          <AppShell />
        </TabsProvider>
      </ConfigProvider>
    </ToastProvider>
  );
}
