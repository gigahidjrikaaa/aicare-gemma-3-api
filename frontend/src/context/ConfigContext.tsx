import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";

export type ClientConfig = {
  baseUrl: string;
  apiKey: string;
  streamingMode: "rest" | "websocket";
};

const STORAGE_KEY = "aicare-config";

const ConfigContext = createContext<{
  config: ClientConfig;
  updateConfig: (partial: Partial<ClientConfig>) => void;
} | null>(null);

const defaultConfig: ClientConfig = {
  baseUrl: (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000",
  apiKey: (import.meta as any).env?.VITE_API_KEY ?? "",
  streamingMode: "rest"
};

type ConfigProviderProps = {
  children: ReactNode;
};

export function ConfigProvider({ children }: ConfigProviderProps) {
  const [config, setConfig] = useState<ClientConfig>(() => {
    if (typeof window === "undefined") {
      return defaultConfig;
    }
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as ClientConfig;
        return { ...defaultConfig, ...parsed };
      }
    } catch (error) {
      console.warn("Failed to parse stored config", error);
    }
    return defaultConfig;
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    }
  }, [config]);

  const updateConfig = useCallback((partial: Partial<ClientConfig>) => {
    setConfig((prev) => ({ ...prev, ...partial }));
  }, []);

  const value = useMemo(() => ({ config, updateConfig }), [config, updateConfig]);

  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export function useClientConfig() {
  const ctx = useContext(ConfigContext);
  if (!ctx) {
    throw new Error("useClientConfig must be used within ConfigProvider");
  }
  return ctx;
}

export function withConfigProvider<T extends object>(Component: React.ComponentType<T>) {
  return function Wrapper(props: T) {
    return (
      <ConfigProvider>
        <Component {...props} />
      </ConfigProvider>
    );
  };
}
