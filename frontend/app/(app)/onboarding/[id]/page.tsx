"use client";

import { useParams } from "next/navigation";
import {
  User,
  RefreshCcw,
  Rocket,
  IdCard,
  Briefcase,
  Sparkles,
} from "lucide-react";

import { useOnboardingDetail } from "@/hooks/useOnboardingDetail";
import { useChecklist } from "@/hooks/useEmployee";

import { ProgressBar } from "@/components/common/ProgressBar";

import { OnboardingChecklist } from "@/components/onboarding/OnboardingChecklist";
import { OnboardingSummaryCards } from "@/components/onboarding/OnboardingSummaryCards";

export default function OnboardingDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const { employee, detail } = useOnboardingDetail(id);
  const { data: checklist } = useChecklist(id);

  if (employee.isLoading || !employee.data) {
    return (
      <div className="page-content text-vantara-text-muted">
        Loading...
      </div>
    );
  }

  const emp = employee.data;
  const od = detail.data;

  const initials = emp.name
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="page-content space-y-5">
      {/* Employee Hero */}

      <div className="ob-hero-card">
        <div className="ob-hero-left">
          <div className="ob-hero-avatar-wrap">
            <div
              className="flex items-center justify-center rounded-full bg-vantara-navy text-white font-medium"
              style={{ width: 64, height: 64, fontSize: 20 }}
            >
              {initials}
            </div>
            <span className="ob-hero-avatar-dot" />
          </div>

          <div>
            <div className="ob-hero-name-row">
              <span className="ob-hero-name">{emp.name}</span>

              <span className="ob-hero-badge">
                <RefreshCcw size={13} strokeWidth={2.5} />
                {od?.status ?? "In Progress"}
              </span>

              <span className="ob-hero-badge">
                <Rocket size={13} strokeWidth={2.5} />
                {od?.type ?? "Onboarding"}
              </span>
            </div>

            <div className="ob-hero-pills">
              <span className="ob-hero-pill">
                <IdCard size={14} strokeWidth={2} />
                {emp.employee_id}
              </span>

              <span className="ob-hero-pill">
                <Briefcase size={14} strokeWidth={2} />
                {emp.title}
              </span>
            </div>
          </div>
        </div>

        <div className="ob-hero-art">
          <div className="ob-hero-art-disc" />

          <div className="ob-hero-art-card">
            <div className="ob-hero-art-card-icon">
              <User size={16} strokeWidth={2} />
            </div>

            <div className="ob-hero-art-card-line" />
            <div
              className="ob-hero-art-card-line"
              style={{ width: 30 }}
            />
          </div>

          <Sparkles
            size={16}
            className="ob-hero-art-sparkle"
            style={{ top: 10, right: 20 }}
          />

          <Sparkles
            size={12}
            className="ob-hero-art-sparkle"
            style={{ bottom: 40, left: 4 }}
          />
        </div>
      </div>

      {/* Summary */}

      <OnboardingSummaryCards
        fields={[
          {
            label: "Manager",
            value: emp.manager,
          },
          {
            label: "Start Date",
            value: od?.startDate ?? emp.start ?? "—",
          },
          {
            label: "Planned Completion",
            value: od?.plannedCompletion ?? emp.est ?? "—",
          },
          {
            label: "Days Remaining",
            value: `${od?.daysRemaining ?? emp.remaining ?? "—"}`,
          },
        ]}
      />

      {/* Progress */}

      <div className="card">
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold text-vantara-navy">
            Overall Progress
          </span>

          <span className="font-semibold text-vantara-navy">
            {emp.progress}%
          </span>
        </div>

        <ProgressBar
          value={emp.progress}
          className="mt-3"
        />
      </div>

      {/* Provisioning Checklist */}

      <div className="card">
        <h3 className="font-semibold text-vantara-navy">
          Onboarding Checklist
        </h3>

        <div className="mt-4">
          <OnboardingChecklist
            items={checklist ?? []}
            employeeId={emp.employee_id}
          />
        </div>
      </div>
    </div>
  );
}