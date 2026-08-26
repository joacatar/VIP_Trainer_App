export type AppRole = 'trainee' | 'trainer'
export type CaseOwner = 'trainee' | 'trainer' | 'none'
export type AttentionState =
  | 'assigned'
  | 'with_trainee'
  | 'needs_trainer'
  | 'approved'

export type CaseStatus =
  | 'not_started'
  | 'assigned'
  | 'submitted'
  | 'in_review'
  | 'corrections_sent'
  | 'awaiting_resubmission'
  | 'approved'
  | 'blocked'

export interface Profile {
  id: string
  full_name: string | null
  role: AppRole
}

export interface Trainee {
  id: string
  full_name: string
  email: string | null
  start_date: string
  timezone: string
  is_test: boolean
  phase_2_started_on: string | null
  auth_user_id: string | null
  current_phase?: string
}

export interface CaseRow {
  id: string
  trainee_id?: string
  phase_no: number
  set_no: number
  case_no: number
  catalog_label: string | null
  order_number: string | null
  source_order_number?: string | null
  journey_category: string | null
  instruction: string | null
  status: CaseStatus
  released_on: string | null
  schedule_due_date: string | null
  due_date: string | null
  estimated_completion_date: string | null
  file_requirements?: Array<{ kind: string; status: string }>
}

export interface FileRequirement {
  id: string
  case_id: string
  kind: string
  status: string
  replacement_reason: string | null
  accepted_at: string | null
  external_url: string | null
  case_files?: CaseFile[]
  latest_file?: CaseFile | null
}

export interface CaseFile {
  id: string
  version_no: number
  storage_path: string
  original_filename: string
  mime_type: string | null
  size_bytes: number | null
  review_status: string | null
  review_note: string | null
  uploaded_at: string
}

export interface HomeworkAssignment {
  id: string
  case_id: string
  title: string
  instructions: string
  status: string
  schedule_due_date: string | null
  due_date: string | null
}

export interface CorrectionThread {
  id: string
  case_id: string
  section: string
  status: string
  related_file: string | null
  created_at: string
  resolved_at: string | null
  correction_events: CorrectionEvent[]
  correction_thread_screenshots?: Screenshot[]
}

export interface CorrectionEvent {
  id: string
  revision_id: string | null
  event_type: string
  body: string
  created_at: string
}

/** A single raised correction, joined out to its thread and case — the
 * shape `listAllRaisedCorrections`/`listRaisedCorrectionsForCases` return.
 * Feeds `lib/domain/correctionAnalytics.ts` for the repeat-correction and
 * per-section/per-trainee breakdowns on both the trainer's Analytics page
 * and the trainee's My corrections page. */
export interface RaisedCorrectionRow {
  id: string
  body: string | null
  created_at: string
  corrections_threads: {
    id: string
    section: string
    status: string
    case_id: string
    created_at: string
    resolved_at: string | null
    cases: {
      id: string
      trainee_id: string
      phase_no: number
      set_no: number
      case_no: number
      catalog_label: string | null
      trainees: { full_name: string } | null
    }
  }
}

export interface Screenshot {
  id: string
  storage_path: string
  original_filename: string
  mime_type: string | null
  size_bytes: number | null
  created_at: string
}

export interface Question {
  id: string
  case_id: string
  trainee_id?: string
  section_key: string | null
  body: string
  answer_body: string | null
  status: string
  created_at: string
  answered_at: string | null
}

export interface TraineeProgress {
  trainee_id: string
  full_name: string
  current_phase: string
  is_test: boolean
  phase_2_started_on: string | null
  total_cases: number
  approved_cases: number
  phase_1_cases: number
  phase_1_approved: number
  phase_2_cases: number
  phase_2_approved: number
  phase_2_unreleased: number
  overdue_cases: number
  waiting_on_trainer: number
  waiting_on_trainee: number
  total_files: number
  accepted_files: number
  estimated_completion_date: string | null
}

export interface CaseResource {
  id: string
  case_id: string
  title: string
  url: string
  resource_type: string
  created_by: string
}
