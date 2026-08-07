"use client";
 
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ColumnDef } from "@tanstack/react-table";
import { Employee } from "@/types/employee";
import { DataTable } from "@/components/common/DataTable";
import { Avatar } from "@/components/common/Avatar";
import { StatusBadge } from "@/components/common/StatusBadge";
 
export function TrackerTable({ employees }: { employees: Employee[] }) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | null>(null);
 
  const goToDetail = (id: string) => {
    router.push(`/onboarding/${id}`);
  };
 
  const columns: ColumnDef<Employee>[] = [
    {
      id: "name",
      header: () => (
        <div className="flex w-full items-center justify-center text-gray-700">Employee</div>
      ),
      accessorKey: "name",
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar name={row.original.name} size={36} />
          <div className="min-w-0">
            <div className="truncate text-[13px] font-semibold text-vantara-navy">
              {row.original.name}
            </div>
            <div className="mt-0.5 text-xs text-vantara-text-muted">
              {row.original.employee_id}
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "dept",
      header: () => (
        <div className="flex w-full items-center justify-center text-gray-700">Department</div>
      ),
      accessorKey: "dept",
      cell: ({ row }) => (
        <div className="flex w-full items-center justify-center">
          <span className="text-[13px] text-vantara-navy">{row.original.dept}</span>
        </div>
      ),
    },
    
    {
      id: "blockers",
      header: () => (
        <div className="flex w-full items-center justify-center text-gray-700">Blockers</div>
      ),
      accessorKey: "blockers",
      cell: ({ row }) => (
        <div className="flex w-full items-center justify-center">
          <span className="text-[13px] text-vantara-navy">{row.original.blockers}</span>
        </div>
      ),
    },
    {
      id: "start",
      header: () => (
        <div className="flex w-full items-center justify-center text-gray-700">Start</div>
      ),
      accessorKey: "start",
      cell: ({ row }) => (
        <div className="flex w-full items-center justify-center">
          <span className="text-[13px] text-vantara-navy">{row.original.start}</span>
        </div>
      ),
    },
    {
      id: "est",
      header: () => (
        <div className="flex w-full items-center justify-center text-gray-700">Est. Completion</div>
      ),
      accessorKey: "est",
      cell: ({ row }) => (
        <div className="flex w-full items-center justify-center">
          <span className="text-[13px] text-vantara-navy">{row.original.est}</span>
        </div>
      ),
    },
    {
      id: "remaining",
      header: () => (
        <div className="flex w-full items-center justify-center text-gray-700">Remaining</div>
      ),
      accessorKey: "remaining",
      cell: ({ row }) => (
        <div className="flex w-full items-center justify-center">
          <span className="text-[13px] font-medium text-vantara-navy">
            {row.original.remaining}d
          </span>
        </div>
      ),
    },
    {
      id: "actions",
      header: () => (
        <div className="flex w-full items-center justify-center text-gray-700">Action</div>
      ),
      cell: ({ row }) => (
        <div className="flex w-full items-center justify-center">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              goToDetail(row.original.id);
            }}
            className="rounded-lg bg-vantara-navy px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-vantara-navy/90"
          >
            View
          </button>
        </div>
      ),
    },
  ];
 
  return (
    <DataTable
      columns={columns}
      data={employees}
      getRowId={(row) => row.id}
      selectedRowId={selectedId}
      onRowClick={(row) => setSelectedId(row.id)}
      gridTemplateColumns="minmax(200px,1.6fr) minmax(100px,0.9fr) minmax(140px,1.1fr) minmax(80px,0.6fr) minmax(80px,0.6fr) minmax(110px,0.9fr) minmax(90px,0.7fr) minmax(70px,0.6fr)"
    />
  );
}
 