export interface DashboardStats {
  total: number;
  completed: number;
  inProgress: number;
  failed: number;
}

export interface IntegrationCoverage {
  realCount: number;
  mockCount: number;
  realPct: number;
  mockPct: number;
  realSystems: string[];
  mockSystems: string[];
}

export interface SlaWarning {
  ticketId: string;
  employee: string;
  department: string;
  item: string;
  duration: string;
}

export interface DepartmentSummary {
  name: string;
  employees: number;
  openTickets: number;
  avgCompletion: number;
}

export interface SystemHealthBrief {
  name: string;
  status: string;
}

export interface TicketStatusSummary {
  open: number;
  inProgress: number;
  pending: number;
  closed: number;
}

export interface DashboardData {
  stats: DashboardStats;
  integrationCoverage: IntegrationCoverage;
  slaWarning: SlaWarning;
  departments: DepartmentSummary[];
  systemHealth: SystemHealthBrief[];
  ticketStatus: TicketStatusSummary;
}

export interface OnboardingAlert {
  id: string;
  severity: "critical" | "high" | "medium";
  title: string;
  body: string;
  kind: "dismiss" | "view" | "ack";
  time?: string;
  date?: string;
}

export interface OnboardingDetail {
  status: string;
  type: string;
  startDate: string;
  plannedCompletion: string;
  daysRemaining: number;
  alerts: OnboardingAlert[];
}

/**
 * Single functional-item provisioning result for one employee, returned by
 * GET /onboarding-details/{employee_id}/provisional-status.
 *
 * Note: per the backend implementation, `ticketID`, `ticketStatus`,
 * `credentials.password`, and `note` are mocked (no ticket/credential/note
 * concept exists for Functional items in the current schema) -- treat them
 * as placeholder data on the frontend, not as live values.
 */
export interface ProvisionalStatusItem {
  platform: string;
  ticketID: string;
  ticketStatus: string;
  startTime: string;
  endtime: string;
  credentials?: {
    username?: string;
    password?: string;
  };
  note?: string;
}

/**
 * Raw shape returned by the provisional-status endpoint, keyed by
 * employee id. Unwrap to ProvisionalStatusItem[] via
 * getProvisionalStatus() -- callers shouldn't need this type directly.
 */
export interface ProvisionalStatusResponse {
  ProvisionalStatus: {
    [employeeId: string]: ProvisionalStatusItem[];
  };
}