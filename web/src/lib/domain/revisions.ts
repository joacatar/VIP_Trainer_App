/** Fixed review sections — port of revisions.py. */

export const REVIEW_SECTIONS = [
  { key: 'scan', label: 'Scan', order: 1 },
  { key: 'rider_form', label: 'Rider form', order: 2 },
  { key: 'segmentation', label: 'Segmentation', order: 3 },
  { key: 'scapula', label: 'Scapula', order: 4 },
  { key: 'glenoid_landmark', label: 'Glenoid landmark', order: 5 },
  { key: 'humeral_landmark', label: 'Humeral landmark', order: 6 },
  { key: 'humeral_implant', label: 'Humeral implant', order: 7 },
  { key: 'glenoid_implant', label: 'Glenoid implant', order: 8 },
] as const

export const SECTION_LABELS: Record<string, string> = Object.fromEntries(
  REVIEW_SECTIONS.map((s) => [s.key, s.label]),
)

/** Sentence-case labels for raw enum values the UI was showing verbatim
 * (e.g. `under_review`, `still_open`) — see the audit's "raw event log"
 * and "raw enum status" findings. */
export const FILE_STATUS_LABELS: Record<string, string> = {
  missing: 'Not sent yet',
  submitted: 'Ready to send',
  under_review: 'With trainer',
  replacement_requested: 'Needs replacement',
  accepted: 'Accepted',
}

export const THREAD_STATUS_LABELS: Record<string, string> = {
  open: 'Open',
  resolved: 'Resolved',
}

export const EVENT_TYPE_LABELS: Record<string, string> = {
  raised: 'Raised',
  still_open: 'Still open',
  resolved: 'Resolved',
  note: 'Note',
}

// Kept byte-for-byte in sync with SECTION_CHECKLISTS in
// src/ct_training_tracker/revisions.py — that file is the source of truth.
// (This copy had drifted from it — humeral_implant/glenoid_implant were
// short placeholder lists instead of the real content. Edit the Python file
// first, then mirror the change here.)
export const SECTION_CHECKLISTS: Record<string, string[]> = {
  scan: [
    'A better scan was available and should have been chosen',
    'This scan is a rejection — it cannot be planned',
  ],
  rider_form: [
    'Rider form is missing required fields',
    'Rider form is not signed',
    'Rider form is missing a comment',
    'Rider form has extra comments',
  ],
  segmentation: [
    'Soft tissue remains around the glenoid rim',
    'Soft tissue remains on the glenoid face',
    'Excessive soft tissue remains around the scapula',
    'A small amount of humeral head remains on the glenoid',
    'A significant portion of humeral head remains on the glenoid',
    // Comparative left as-is on purpose — the correct threshold/cortex
    // choice is a clinical judgment call this checklist can't specify.
    'Better thresholding choice was available',
    'Better cortex choice was available for choosing',
  ],
  scapula: [
    'Minor movement to glenoid center',
    'Minor movement to trigonum scapula',
    'Minor movement to angulus inferior',
    'The angulus inferior needs to be on the cortex',
    'The angulus inferior needs to be centered in the last slice of the transverse view',
    'Glenoid center is only centered in one view — check both',
    'Glenoid Center needs to be more superior',
    'Two or more landmarks need major repositioning — specify which',
    'SN should be on the neck',
  ],
  glenoid_landmark: [
    'Minor movement of anterior glenoid rim landmark',
    'Minor movement of posterior glenoid rim landmark',
    'Minor movement of superior glenoid rim landmark',
    'Glenoid plane is too expanded',
    'Glenoid plane is too cramped',
    'Version should be updated to mimic native vault',
    // Direction left as-is on purpose — same clinical-judgment caveat as
    // the segmentation "Better ... choice" pair above.
    'Major change to version',
    'Major change to inclination',
    'Reset glenoid plane landmarks to new locations',
    'Forgot to set some coracoid / acromion / scapular neck landmarks',
    'GRA and GRP are not in the same plane',
  ],
  humeral_landmark: [
    // Left as-is on purpose — "what changed" is a clinical judgment call
    // this checklist can't specify.
    'Minor correction to humeral shaft',
    'Major correction to humeral shaft',
    'Shaft landmarks should not be deep onto the axis canal, they should mimic the implant length',
    'Humeral plane directed more through humeral head',
    'Humeral plane changed Neck Shaft Angle',
    'Slight change to other humeral landmarks',
    'Forgot to place one or more other humeral landmarks',
    'AN landmark should be on solid bone on the calcar area',
    'Humeral head size needs to be reduced',
    'Humeral head size needs to be increased',
    'Humeral head size not centered',
  ],
  humeral_implant: [
    'Humeral stem selection not appropriate for anatomy',
    'Cage Screw should be reduced until it is small; it has to have at least 8mm gap with the cortex',
    'Eclipse can be closer to the cortex to mimic the articulating surface better',
    'Cup head of stem should match glenosphere size',
  ],
  glenoid_implant: [
    'Need to update implant due to changes in landmarks',
    'Rolled to better superior implant trajectory',
    'Implant version needs to be updated',
    'Implant inclination needs to be updated',
    'Implant positioning should be inferior and posterior avoiding unstable bone',
    'VL implant should be more centered into the glenoid anatomy; it should follow and sit onto the anatomy',
    'VL roll should change to mimic anatomy better',
    'Implant downsizing unnecessary',
    'Avoid perforating the polyethylene component (VL)',
    'Reduce medialization into the glenoid',
    'Backside seating should reach 100% — it does not yet',
    'AP Measurement is missing for glenosphere size',
    // 'Glenosphere size is incorrect' removed — redundant with the two
    // directional chips right below, which already cover it.
    'Glenosphere size is too small',
    'Glenosphere size is too large',
    'The usage of half augments is not permitted',
  ],
}

export const FILE_KIND_LABELS: Record<string, string> = {
  pdf_primary: 'PDF 1',
  pdf_secondary: 'PDF 2',
  ov: 'OV',
}
