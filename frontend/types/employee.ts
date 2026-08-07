import { OnboardingAlert } from "./onboarding";

export interface Employee {
  id: string;
  name: string;
  dept: string;
  type: "experienced" | "fresher";
  employee_id: string;
  manager: string;
  status: string;
  progress: number;
  blockers: number;
  start: string | null;
  est: string | null;
  remaining: number | null;
  email: string;
  phone: string;
  office: string;
  empManager: string;
  hireDate: string;
  yearsOfService: string;
  jobLevel: string;
  title: string;
}

export type ChecklistStatus =
  | "done"
  | "inProgress"
  | "failed"
  | "blocked"
  | "pending";

export interface ChecklistItem {
  system: string;
  platform: string;
  status: ChecklistStatus;
  detail: string;
  outcome: string;

  // Common Response
  responseTitle?: string;
  requestStatus?: string;
  endpoint?: string;
  responseTime?: string;
  executedAt?: string;
  executedBy?: string;

  // Keycloak
  userId?: string;
  username?: string;
  realm?: string;
  role?: string;

  // MailU
  mailbox?: string;
  domain?: string;
  quota?: string;

  // Kimai
  employeeId?: string;
  timesheetStatus?: string;
  defaultProject?: string;

  // Snipe-IT
  assetTag?: string;
  assetType?: string;
  serialNumber?: string;
  assignedTo?: string;
  checkoutStatus?: string;

  // Steps
  steps?: string[];

  // Existing alert support
  alert?: OnboardingAlert;
}

export type { OnboardingAlert };