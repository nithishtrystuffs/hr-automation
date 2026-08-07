"use client";

import { useEffect, useMemo } from "react";
import { ListChecks } from "lucide-react";
import { useOnboarding } from "@/hooks/useOnboarding";
import { useTrackerStore } from "@/store/trackerStore";
import { useHeaderStore } from "@/store/headerStore";
import { TrackerTable } from "@/components/onboarding/TrackerTable";
import { Input } from "@/components/ui/input";
import { SimpleSelect } from "@/components/ui/select";

export default function OnboardingTrackerPage() {
  const { data: employees, isLoading } = useOnboarding();
  const { search, dept, setSearch, setDept } = useTrackerStore();
  const setHeader = useHeaderStore((s) => s.setHeader);

  useEffect(() => {
    setHeader({
      title: "Onboarding tracker",
      subtitle: "Track provisioning progress for every employee in flight",
      icon: <ListChecks size={22} strokeWidth={2} />,
    });
  }, [setHeader]);


  const depts = useMemo(() => {
    if (!employees) return ["All"];
    const unique = Array.from(new Set(employees.map((e) => e.dept))).sort();
    return ["All", ...unique];
  }, [employees]);

  const filtered = useMemo(() => {
    if (!employees) return [];
    return employees.filter((e) => {
      const matchesSearch =
        !search ||
        e.name.toLowerCase().includes(search.toLowerCase()) ||
        e.id.toLowerCase().includes(search.toLowerCase());
      const matchesDept = dept === "All" || e.dept === dept;
      return matchesSearch && matchesDept;
    });
  }, [employees, search, dept]);

  return (
    <main className="directory-bg flex-1 overflow-hidden">
      <div className="page-content h-full">
        <div className="directory-panel flex h-full flex-col">
          <div
            className="directory-toolbar shrink-0"
            style={{ padding: "10px 14px", gap: "10px", alignItems: "center" }}
          >
            <Input
              className="directory-search"
              placeholder="Search by name or ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ height: "34px", padding: "0 10px", fontSize: "13px" }}
            />

            <SimpleSelect
              className="directory-select"
              options={depts}
              value={dept}
              onChange={(e) => setDept(e.target.value)}
              style={{ height: "34px", padding: "0 10px", fontSize: "13px" }}
            />

            <span
              className="directory-count-pill"
              style={{
                padding: "6px 14px",
                fontSize: "13px",
                height: "34px",
                display: "inline-flex",
                alignItems: "center",
              }}
            >
              {filtered.length} Employees
            </span>
          </div>

          <div className="directory-card flex-1 !p-0">
            {isLoading ? (
              <div className="flex h-full items-center justify-center text-vantara-text-muted">
                Loading tracker...
              </div>
            ) : (
              <TrackerTable employees={filtered} />
            )}
          </div>
        </div>
      </div>
    </main>
  );
}