import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type TabsContextValue = {
  activeTab: string;
  setActiveTab: (tab: string) => void;
};

const TabsContext = createContext<TabsContextValue | undefined>(undefined);

type TabsProviderProps = {
  children: ReactNode;
  defaultTab: string;
};

export function TabsProvider({ children, defaultTab }: TabsProviderProps) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  const value = useMemo(() => ({ activeTab, setActiveTab }), [activeTab]);
  return <TabsContext.Provider value={value}>{children}</TabsContext.Provider>;
}

export function useTabs() {
  const ctx = useContext(TabsContext);
  if (!ctx) {
    throw new Error("useTabs must be used within TabsProvider");
  }
  return ctx;
}
