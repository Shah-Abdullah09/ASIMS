/** Staff roles and the work queue each one sees (the server decides which cases are in it). */
export const PLACEMENT = ['placement_officer', 'administrator']
export const STAFF = [...PLACEMENT, 'dac_member', 'director', 'registrar', 'vice_chancellor']

export const QUEUES = {
  placement_officer: {
    title: 'Scholarship applications',
    hint: 'Every submitted Need Based Financial Grant application: verify documents, return, forward and track.',
  },
  administrator: {
    title: 'Scholarship applications',
    hint: 'Every submitted application at every stage. You can take the Placement Office actions.',
  },
  dac_member: {
    title: 'DAC review queue',
    hint: 'Applications from your department waiting for the interview and the shortlisting decision.',
  },
  director: { title: 'Director review queue', hint: 'Shortlisted cases waiting for your approval.' },
  registrar: { title: 'Registrar review queue', hint: 'Cases approved by the Director, waiting for your approval.' },
  vice_chancellor: { title: 'VC review queue', hint: 'Cases approved by the Registrar, waiting for the final approval.' },
}

export const FLAG_SECTIONS = [
  ['personal', 'Personal details'], ['household', 'Family'], ['parents', 'Parents & guardian'], ['income', 'Income'],
  ['accommodation', 'Accommodation'], ['expenses', 'Expenditure'], ['assets', 'Assets & financing'],
  ['education', 'Education'], ['undertaking', 'Undertaking'], ['form2', 'Form 2 scan'],
]
