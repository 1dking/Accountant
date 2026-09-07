import { api } from './client'
import type { ApiResponse } from '@/types/api'

export type PayType = 'hourly' | 'salary'
export type PayFrequency = 'weekly' | 'biweekly' | 'semimonthly' | 'monthly'
export type EmployeeStatus = 'active' | 'on_leave' | 'terminated'
export type RunStatus = 'draft' | 'approved' | 'paid' | 'void'

export const PAY_PERIODS: Record<PayFrequency, number> = { weekly: 52, biweekly: 26, semimonthly: 24, monthly: 12 }

export interface Employee {
  id: string
  first_name: string
  last_name: string
  full_name: string
  email: string | null
  phone: string | null
  sin_masked: string | null
  date_of_birth: string | null
  address_line1: string | null
  address_line2: string | null
  city: string | null
  province: string | null
  postal_code: string | null
  hire_date: string
  termination_date: string | null
  status: EmployeeStatus
  job_title: string | null
  province_of_employment: string
  pay_type: PayType
  pay_rate: string
  pay_frequency: PayFrequency
  default_hours_per_period: string | null
  td1_federal_claim: string | null
  td1_provincial_claim: string | null
  additional_tax_per_period: string
  cpp_exempt: boolean
  ei_exempt: boolean
  vacation_pay_pct: string
  vacation_pay_each_period: boolean
  vacation_accrued_balance: string
  notes: string | null
  contact_id: string | null
  created_at: string
  updated_at: string
}

export interface EmployeeInput {
  first_name: string
  last_name: string
  email?: string | null
  phone?: string | null
  sin?: string | null
  date_of_birth?: string | null
  address_line1?: string | null
  address_line2?: string | null
  city?: string | null
  province?: string | null
  postal_code?: string | null
  hire_date: string
  termination_date?: string | null
  status?: EmployeeStatus
  job_title?: string | null
  province_of_employment: string
  pay_type: PayType
  pay_rate: number
  pay_frequency: PayFrequency
  default_hours_per_period?: number | null
  td1_federal_claim?: number | null
  td1_provincial_claim?: number | null
  additional_tax_per_period?: number
  cpp_exempt?: boolean
  ei_exempt?: boolean
  vacation_pay_pct?: number
  vacation_pay_each_period?: boolean
  notes?: string | null
}

export interface PayStub {
  id: string
  run_id: string
  employee_id: string
  employee_name: string | null
  hours: string | null
  rate: string
  regular_pay: string
  overtime_pay: string
  bonus: string
  vacation_pay: string
  other_earnings: string
  gross: string
  cpp_employee: string
  cpp2_employee: string
  ei_employee: string
  qpip_employee: string
  federal_tax: string
  provincial_tax: string
  other_deductions: string
  net_pay: string
  cpp_employer: string
  cpp2_employer: string
  ei_employer: string
  qpip_employer: string
  insurable_earnings: string
  insurable_hours: string
  pensionable_earnings: string
  ytd_gross: string
  ytd_cpp_employee: string
  ytd_cpp2_employee: string
  ytd_ei_employee: string
  ytd_qpip_employee: string
  ytd_federal_tax: string
  ytd_provincial_tax: string
  ytd_insurable_earnings: string
  ytd_pensionable_earnings: string
  ytd_net: string
  province_of_employment: string
  tables_version: string
  pdf_storage_path: string | null
  notes: string | null
}

export interface PayrollRun {
  id: string
  period_start: string
  period_end: string
  pay_date: string
  pay_frequency: PayFrequency
  status: RunStatus
  total_gross: string
  total_vacation_pay: string
  total_cpp_employee: string
  total_cpp_employer: string
  total_ei_employee: string
  total_ei_employer: string
  total_federal_tax: string
  total_provincial_tax: string
  total_other_deductions: string
  total_net: string
  total_remittance: string
  journal_entry_id: string | null
  approved_at: string | null
  paid_at: string | null
  notes: string | null
  stubs: PayStub[]
  created_at: string
  updated_at: string
}

export interface RunSummary {
  id: string
  period_start: string
  period_end: string
  pay_date: string
  pay_frequency: PayFrequency
  status: RunStatus
  total_gross: string
  total_net: string
  total_remittance: string
  stub_count: number
  created_at: string
}

export interface StubOverride {
  employee_id: string
  hours?: number | null
  overtime_pay?: number
  bonus?: number
  other_earnings?: number
  other_deductions?: number
  vacation_payout?: number
  notes?: string | null
}

export interface RunCreate {
  period_start: string
  period_end: string
  pay_date: string
  pay_frequency: PayFrequency
  employee_ids?: string[] | null
  overrides?: StubOverride[]
  notes?: string | null
}

export interface PreviewInput {
  province_of_employment: string
  pay_frequency: PayFrequency
  pay_type: PayType
  pay_rate: number
  hours?: number | null
  vacation_pay_pct?: number
}

export interface Preview {
  gross: string
  cpp_employee: string
  cpp2_employee: string
  ei_employee: string
  qpip_employee: string
  federal_tax: string
  provincial_tax: string
  net_pay: string
  employer_cpp: string
  employer_ei: string
  employer_qpip: string
  total_employer_cost: string
  annual_taxable_income: string
  tables_version: string
}

export interface Remittance {
  year: number
  month: number
  run_count: number
  gross_payroll: string
  employee_count: number
  cpp_employee: string
  cpp_employer: string
  ei_employee: string
  ei_employer: string
  income_tax: string
  total_cra: string
  total_revenu_quebec: string
  due_date: string
}

// ── Employees ──

export function listEmployees(includeTerminated = false) {
  return api.get<ApiResponse<Employee[]>>(`/payroll/employees${includeTerminated ? '?include_terminated=true' : ''}`)
}
export function createEmployee(data: EmployeeInput) {
  return api.post<ApiResponse<Employee>>('/payroll/employees', data)
}
export function updateEmployee(id: string, data: Partial<EmployeeInput>) {
  return api.put<ApiResponse<Employee>>(`/payroll/employees/${id}`, data)
}
export function deleteEmployee(id: string) {
  return api.delete<ApiResponse<{ detail: string }>>(`/payroll/employees/${id}`)
}

// ── Runs ──

export function listRuns(year?: number) {
  return api.get<ApiResponse<RunSummary[]>>(`/payroll/runs${year ? `?year=${year}` : ''}`)
}
export function getRun(id: string) {
  return api.get<ApiResponse<PayrollRun>>(`/payroll/runs/${id}`)
}
export function createRun(data: RunCreate) {
  return api.post<ApiResponse<PayrollRun>>('/payroll/runs', data)
}
export function recalculateRun(id: string, overrides: StubOverride[]) {
  return api.post<ApiResponse<PayrollRun>>(`/payroll/runs/${id}/recalculate`, overrides)
}
export function approveRun(id: string) {
  return api.post<ApiResponse<PayrollRun>>(`/payroll/runs/${id}/approve`)
}
export function markRunPaid(id: string) {
  return api.post<ApiResponse<PayrollRun>>(`/payroll/runs/${id}/mark-paid`)
}
export function voidRun(id: string) {
  return api.post<ApiResponse<PayrollRun>>(`/payroll/runs/${id}/void`)
}

// ── Preview + remittance ──

export function previewPay(data: PreviewInput) {
  return api.post<ApiResponse<Preview>>('/payroll/preview', data)
}
export function getRemittance(year: number, month: number) {
  return api.get<ApiResponse<Remittance>>(`/payroll/remittance?year=${year}&month=${month}`)
}
