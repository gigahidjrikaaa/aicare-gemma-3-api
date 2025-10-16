type TabConfig = {
  id: string;
  label: string;
  component: () => JSX.Element;
};

type TabViewProps = {
  tabs: TabConfig[];
  activeTab: string;
  onTabChange: (tab: string) => void;
};

export function TabView({ tabs, activeTab, onTabChange }: TabViewProps) {
  const ActiveComponent = tabs.find((tab) => tab.id === activeTab)?.component ?? tabs[0]?.component;
  return (
    <div className="flex flex-col gap-4">
      <nav className="flex flex-wrap gap-2">
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                isActive ? "bg-emerald-500 text-slate-950" : "bg-slate-800 text-slate-200 hover:bg-slate-700"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>
      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 shadow-lg">
        {ActiveComponent ? <ActiveComponent /> : null}
      </section>
    </div>
  );
}
