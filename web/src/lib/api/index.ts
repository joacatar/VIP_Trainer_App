import { supabase, CASE_FILES_BUCKET } from '../supabase'
import { screenshotStoragePath } from '../domain/screenshots'
import type {
  CaseResource,
  CaseRow,
  CorrectionThread,
  FileRequirement,
  HomeworkAssignment,
  Profile,
  Question,
  RaisedCorrectionRow,
  Trainee,
  TraineeProgress,
} from '../types'

const RAISED_CORRECTION_COLS =
  'id, body, created_at, corrections_threads!inner(id, section, status, case_id, created_at, resolved_at, cases!inner(id, trainee_id, phase_no, set_no, case_no, catalog_label, trainees(full_name)))'

const CASE_COLS =
  'id, trainee_id, phase_no, set_no, case_no, catalog_label, order_number, journey_category, instruction, phase, released_on, status, schedule_due_date, due_date, estimated_completion_date'

const CASE_COLS_WITH_FILES = `${CASE_COLS}, file_requirements(kind, status)`
const CASE_COLS_TRAINER = `${CASE_COLS}, source_order_number`

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

export async function getProfile(userId: string): Promise<Profile | null> {
  const { data, error } = await supabase
    .from('profiles')
    .select('id, full_name, role')
    .eq('id', userId)
    .maybeSingle()
  if (error) throw error
  return data as Profile | null
}

export async function listProgress(): Promise<TraineeProgress[]> {
  const { data, error } = await supabase
    .from('trainee_progress')
    .select('*')
    .order('full_name')
  if (error) throw error
  return (data ?? []) as TraineeProgress[]
}

export async function listActiveTrainees(): Promise<Trainee[]> {
  const { data, error } = await supabase
    .from('trainees')
    .select(
      'id, full_name, email, start_date, timezone, is_test, phase_2_started_on, auth_user_id, current_phase',
    )
    .eq('active', true)
    .order('full_name')
  if (error) throw error
  return (data ?? []) as Trainee[]
}

export async function getTraineeForUser(userId: string): Promise<Trainee | null> {
  const { data, error } = await supabase
    .from('trainees')
    .select(
      'id, full_name, email, start_date, timezone, is_test, phase_2_started_on, auth_user_id, current_phase',
    )
    .eq('auth_user_id', userId)
    .maybeSingle()
  if (error) throw error
  return data as Trainee | null
}

export async function getTrainee(traineeId: string): Promise<Trainee | null> {
  const { data, error } = await supabase
    .from('trainees')
    .select(
      'id, full_name, email, start_date, timezone, is_test, phase_2_started_on, auth_user_id, current_phase',
    )
    .eq('id', traineeId)
    .maybeSingle()
  if (error) throw error
  return data as Trainee | null
}

export async function createTrainee(input: {
  full_name: string
  email: string | null
  start_date: string
  timezone: string
  created_by: string
  is_test?: boolean
}): Promise<string> {
  const { data, error } = await supabase
    .from('trainees')
    .insert({
      full_name: input.full_name,
      email: input.email,
      start_date: input.start_date,
      timezone: input.timezone,
      created_by: input.created_by,
      is_test: input.is_test ?? false,
    })
    .select('id')
    .single()
  if (error) throw error
  return data.id as string
}

export async function listCases(
  traineeId: string,
  opts: {
    includeFiles?: boolean
    includeSource?: boolean
    phaseNo?: number | null
    releasedOnly?: boolean
  } = {},
): Promise<CaseRow[]> {
  let cols = CASE_COLS
  if (opts.includeFiles) cols = CASE_COLS_WITH_FILES
  if (opts.includeSource) cols = `${CASE_COLS_TRAINER}${opts.includeFiles ? ', file_requirements(kind, status)' : ''}`

  let query = supabase
    .from('cases')
    .select(cols)
    .eq('trainee_id', traineeId)
    .order('phase_no')
    .order('set_no')
    .order('case_no')

  if (opts.phaseNo != null) query = query.eq('phase_no', opts.phaseNo)
  if (opts.releasedOnly) query = query.lte('released_on', todayIso())

  const { data, error } = await query
  if (error) throw error
  return (data ?? []) as unknown as CaseRow[]
}

export async function getCase(
  caseId: string,
  opts: { includeFiles?: boolean; includeSource?: boolean } = {},
): Promise<CaseRow | null> {
  let cols = CASE_COLS
  if (opts.includeSource) cols = CASE_COLS_TRAINER
  if (opts.includeFiles) cols = `${cols}, file_requirements(kind, status)`

  const { data, error } = await supabase
    .from('cases')
    .select(cols)
    .eq('id', caseId)
    .maybeSingle()
  if (error) throw error
  return data as CaseRow | null
}

export async function assignHomework(input: {
  caseId: string
  title: string
  instructions: string
  scheduleDueDate: string
  dueDate: string
}): Promise<string> {
  const { data, error } = await supabase.rpc('assign_homework', {
    target_case_id: input.caseId,
    homework_title: input.title,
    homework_instructions: input.instructions,
    scheduled_due: input.scheduleDueDate,
    assigned_due: input.dueDate,
  })
  if (error) throw error
  return data as string
}

export async function listHomeworkForCases(
  caseIds: string[],
): Promise<HomeworkAssignment[]> {
  if (!caseIds.length) return []
  const { data, error } = await supabase
    .from('homework_assignments')
    .select(
      'id, case_id, title, instructions, status, schedule_due_date, due_date',
    )
    .in('case_id', caseIds)
    .neq('status', 'cancelled')
    .order('due_date')
  if (error) throw error
  return (data ?? []) as HomeworkAssignment[]
}

export async function bulkUpdateDueDates(
  updates: Array<{ caseId: string; dueDate: string }>,
): Promise<string[]> {
  const failed: string[] = []
  for (const u of updates) {
    try {
      const { error: e1 } = await supabase
        .from('cases')
        .update({ due_date: u.dueDate })
        .eq('id', u.caseId)
      if (e1) throw e1
      const { error: e2 } = await supabase
        .from('homework_assignments')
        .update({ due_date: u.dueDate })
        .eq('case_id', u.caseId)
      if (e2) throw e2
    } catch {
      failed.push(u.caseId)
    }
  }
  return failed
}

export async function listRequirementsForCase(
  caseId: string,
): Promise<FileRequirement[]> {
  const { data, error } = await supabase
    .from('file_requirements')
    .select(
      'id, case_id, kind, status, replacement_reason, accepted_at, external_url, case_files(id, version_no, storage_path, original_filename, mime_type, size_bytes, review_status, review_note, uploaded_at)',
    )
    .eq('case_id', caseId)
    .order('kind')
  if (error) throw error
  const rows = (data ?? []) as FileRequirement[]
  for (const row of rows) {
    const versions = [...(row.case_files ?? [])].sort(
      (a, b) => (a.version_no ?? 0) - (b.version_no ?? 0),
    )
    row.case_files = versions
    row.latest_file = versions.at(-1) ?? null
  }
  return rows
}

export async function markFileSent(
  requirementId: string,
  shareUrl: string | null,
): Promise<void> {
  const { error } = await supabase.rpc('mark_file_sent', {
    target_requirement_id: requirementId,
    share_url: shareUrl,
  })
  if (error) throw error
}

export async function unmarkFileSent(requirementId: string): Promise<void> {
  const { error } = await supabase.rpc('unmark_file_sent', {
    target_requirement_id: requirementId,
  })
  if (error) throw error
}

export async function reviewFileRequirement(input: {
  requirementId: string
  decision: string
  note?: string
}): Promise<void> {
  const { error } = await supabase.rpc('review_file_requirement', {
    target_requirement_id: input.requirementId,
    decision: input.decision,
    decision_note: input.note ?? '',
  })
  if (error) throw error
}

export async function submitCaseForReview(caseId: string): Promise<void> {
  const { error } = await supabase.rpc('submit_case_for_review', {
    target_case_id: caseId,
  })
  if (error) throw error
}

export async function publishCaseReview(input: {
  caseId: string
  revisionId?: string | null
  fileDecisions?: Array<{ requirement_id: string; decision: string; note?: string }>
  approvePackage?: boolean
}): Promise<void> {
  const { error } = await supabase.rpc('publish_case_review', {
    target_case_id: input.caseId,
    target_revision_id: input.revisionId ?? null,
    file_decisions: input.fileDecisions ?? [],
    approve_package: input.approvePackage ?? false,
  })
  if (error) throw error
}

export async function listCorrectionThreads(
  caseId: string,
  status?: string,
): Promise<CorrectionThread[]> {
  let query = supabase
    .from('corrections_threads')
    .select(
      'id, case_id, section, status, related_file, created_at, resolved_at, resolved_in_revision_id, correction_events(id, revision_id, event_type, body, created_at), correction_thread_screenshots(id, storage_path, original_filename, mime_type, size_bytes, created_at)',
    )
    .eq('case_id', caseId)
    .order('created_at')
  if (status) query = query.eq('status', status)
  const { data, error } = await query
  if (error) throw error
  const rows = (data ?? []) as CorrectionThread[]
  for (const t of rows) {
    t.correction_events = [...(t.correction_events ?? [])].sort((a, b) =>
      a.created_at.localeCompare(b.created_at),
    )
  }
  return rows
}

export async function createCorrectionThread(input: {
  caseId: string
  section: string
  body: string
  revisionId?: string | null
  relatedFile?: string | null
}): Promise<string> {
  const { data, error } = await supabase.rpc('create_correction_thread', {
    target_case_id: input.caseId,
    target_section: input.section,
    thread_body: input.body,
    target_revision_id: input.revisionId ?? null,
    target_related_file: input.relatedFile ?? null,
  })
  if (error) throw error
  return data as string
}

export async function addCorrectionEvent(input: {
  threadId: string
  revisionId?: string | null
  eventType: string
  body: string
}): Promise<void> {
  const { error } = await supabase.from('correction_events').insert({
    thread_id: input.threadId,
    revision_id: input.revisionId ?? null,
    event_type: input.eventType,
    body: input.body,
  })
  if (error) throw error
}

// `target_revision_id` has no default on either SQL function (see
// 20260804090000_correction_threads.sql) — omitting it doesn't fall back to
// null, it makes PostgREST unable to find a matching function overload at
// all (PGRST202, 404: "Could not find the function ... in the schema
// cache"). Both calls below were missing it. `revisionId` is optional here
// because resolving/reopening a thread outside of an active review pass
// (no draft revision yet) is a legitimate case — pass whatever the caller
// has, null included.
export async function resolveThread(
  threadId: string,
  revisionId?: string | null,
): Promise<void> {
  const { error } = await supabase.rpc('resolve_correction_thread', {
    target_thread_id: threadId,
    target_revision_id: revisionId ?? null,
  })
  if (error) throw error
}

export async function reopenThread(
  threadId: string,
  revisionId?: string | null,
): Promise<void> {
  const { error } = await supabase.rpc('reopen_correction_thread', {
    target_thread_id: threadId,
    target_revision_id: revisionId ?? null,
  })
  if (error) throw error
}

export async function markOpenThreadsStillOpen(
  caseId: string,
  revisionId: string,
): Promise<number> {
  const { data, error } = await supabase.rpc('mark_open_threads_still_open', {
    target_case_id: caseId,
    target_revision_id: revisionId,
  })
  if (error) throw error
  return Number(data ?? 0)
}

/** Trainer-only (RLS: corrections_threads "manage" policy requires
 * is_trainer()) — every correction ever raised, across every trainee. Feeds
 * the "Overall" analytics tab. */
export async function listAllRaisedCorrections(): Promise<RaisedCorrectionRow[]> {
  const { data, error } = await supabase
    .from('correction_events')
    .select(RAISED_CORRECTION_COLS)
    .eq('event_type', 'raised')
    .order('created_at', { ascending: false })
  if (error) throw error
  return (data ?? []) as unknown as RaisedCorrectionRow[]
}

/** Corrections raised on a specific set of cases — used for the trainee's
 * own "My corrections" page. RLS (`corrections_threads_trainees_read_published`)
 * already limits a trainee to their own cases and to threads that touched a
 * published revision, so this is safe to call with just the trainee's own
 * case ids. */
export async function listRaisedCorrectionsForCases(
  caseIds: string[],
): Promise<RaisedCorrectionRow[]> {
  if (!caseIds.length) return []
  const { data, error } = await supabase
    .from('correction_events')
    .select(RAISED_CORRECTION_COLS)
    .eq('event_type', 'raised')
    .in('corrections_threads.case_id', caseIds)
    .order('created_at', { ascending: false })
  if (error) throw error
  return (data ?? []) as unknown as RaisedCorrectionRow[]
}

export async function getCaseOwnerUserId(caseId: string): Promise<string | null> {
  const { data, error } = await supabase
    .from('cases')
    .select('trainees(auth_user_id)')
    .eq('id', caseId)
    .maybeSingle()
  if (error) throw error
  const trainee = data?.trainees as { auth_user_id?: string | null } | null
  return trainee?.auth_user_id ?? null
}

/** Trainer-only (RLS: `correction_thread_screenshots` "manage" policy
 * requires is_trainer()) — pastes/uploads a screenshot onto a correction
 * thread, matching Streamlit's Jira-style comment box. Stored under the
 * trainee's own auth-user folder (see screenshots.ts), not the trainer's,
 * so trainee reads keep working under the existing storage RLS policy.
 * Rolls the upload back if the row insert fails, same as
 * `upload_thread_screenshot` in repository.py. */
export async function uploadThreadScreenshot(input: {
  threadId: string
  caseId: string
  ownerUserId: string
  uploadedBy: string
  file: File
}): Promise<void> {
  if (!input.ownerUserId) {
    throw new Error(
      'Cannot upload screenshot: trainee has no linked auth account (auth_user_id). Link their email first.',
    )
  }
  const objectPath = screenshotStoragePath({
    ownerUserId: input.ownerUserId,
    caseId: input.caseId,
    threadId: input.threadId,
    filename: input.file.name,
  })
  const { error: uploadError } = await supabase.storage
    .from(CASE_FILES_BUCKET)
    .upload(objectPath, input.file, {
      contentType: input.file.type || 'application/octet-stream',
      upsert: false,
    })
  if (uploadError) throw uploadError

  const { error: insertError } = await supabase
    .from('correction_thread_screenshots')
    .insert({
      thread_id: input.threadId,
      storage_path: objectPath,
      original_filename: objectPath.split('/').pop(),
      mime_type: input.file.type || null,
      size_bytes: input.file.size,
      uploaded_by: input.uploadedBy,
    })
  if (insertError) {
    await supabase.storage.from(CASE_FILES_BUCKET).remove([objectPath])
    throw insertError
  }
}

/** case-files is a private bucket — every read goes through a short-lived
 * signed URL rather than a public one. */
export async function getScreenshotSignedUrl(
  storagePath: string,
  expiresInSeconds = 600,
): Promise<string> {
  const { data, error } = await supabase.storage
    .from(CASE_FILES_BUCKET)
    .createSignedUrl(storagePath, expiresInSeconds)
  if (error) throw error
  return data.signedUrl
}

export async function listQuestionsForCase(caseId: string): Promise<Question[]> {
  const { data, error } = await supabase
    .from('questions')
    .select(
      'id, case_id, trainee_id, section_key, body, answer_body, status, created_at, answered_at',
    )
    .eq('case_id', caseId)
    .order('created_at', { ascending: false })
  if (error) throw error
  return (data ?? []) as Question[]
}

export async function listQuestionsForTrainee(
  traineeId: string,
): Promise<Question[]> {
  const { data, error } = await supabase
    .from('questions')
    .select(
      'id, case_id, trainee_id, section_key, body, answer_body, status, created_at, answered_at',
    )
    .eq('trainee_id', traineeId)
    .order('created_at', { ascending: false })
  if (error) throw error
  return (data ?? []) as Question[]
}

export async function listQuestionsForTrainer(): Promise<Question[]> {
  const { data, error } = await supabase
    .from('questions')
    .select(
      'id, case_id, trainee_id, section_key, body, answer_body, status, created_at, answered_at',
    )
    .in('status', ['open', 'answered'])
    .order('created_at', { ascending: false })
  if (error) throw error
  return (data ?? []) as Question[]
}

export async function askQuestion(input: {
  caseId: string
  body: string
  sectionKey?: string | null
}): Promise<string> {
  const params: Record<string, string> = {
    target_case_id: input.caseId,
    question_body: input.body,
  }
  if (input.sectionKey) params.target_section_key = input.sectionKey
  const { data, error } = await supabase.rpc('ask_question', params)
  if (error) throw error
  return data as string
}

export async function answerQuestion(
  questionId: string,
  answerBody: string,
): Promise<void> {
  const { error } = await supabase.rpc('answer_question', {
    target_question_id: questionId,
    response_body: answerBody,
  })
  if (error) throw error
}

export async function setQuestionStatus(
  questionId: string,
  status: string,
): Promise<void> {
  const { error } = await supabase.rpc('set_question_status', {
    target_question_id: questionId,
    next_status: status,
  })
  if (error) throw error
}

export async function markQuestionViewed(questionId: string): Promise<void> {
  const { error } = await supabase.rpc('mark_question_viewed', {
    target_question_id: questionId,
  })
  if (error) throw error
}

export async function listCaseResources(caseId: string): Promise<CaseResource[]> {
  const { data, error } = await supabase
    .from('case_resources')
    .select('id, case_id, title, url, resource_type, created_by')
    .eq('case_id', caseId)
    .order('created_at')
  if (error) throw error
  return (data ?? []) as CaseResource[]
}

export async function createRevision(caseId: string): Promise<string> {
  const { data, error } = await supabase.rpc('create_revision', {
    target_case_id: caseId,
  })
  if (error) throw error
  return data as string
}

export async function listRevisionsForCase(caseId: string) {
  const { data, error } = await supabase
    .from('revisions')
    .select('id, case_id, status, created_at, published_at')
    .eq('case_id', caseId)
    .order('created_at', { ascending: false })
  if (error) throw error
  return data ?? []
}
