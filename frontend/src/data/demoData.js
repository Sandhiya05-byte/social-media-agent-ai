export const sidebarItems = [
  { label: 'Command Center', icon: 'LayoutDashboard', active: true },
  { label: 'Agent Control Room', icon: 'Sparkles' },
  { label: 'Intelligence Hub', icon: 'Radar' },
  { label: 'Content Studio', icon: 'Folders' },
  { label: 'Creator Avatar Studio', icon: 'Wand2' },
  { label: 'Publishing Calendar', icon: 'CalendarClock' },
  { label: 'Analytics', icon: 'BarChart3' },
  { label: 'Creator Settings', icon: 'Settings' },
];

export const agentStatus = [
  { name: 'Trend Research Agent', status: 'Active', score: '92%', detail: 'Niche signals refreshed 8 minutes ago.' },
  { name: 'Competitor Intelligence', status: 'Reviewing', score: '87%', detail: '7 public posts analyzed in the last 24h.' },
  { name: 'Brand Voice Agent', status: 'Synced', score: '94%', detail: 'Voice profile aligned to approved examples.' },
  { name: 'Hook Generation', status: 'Running', score: '89%', detail: '3 hook options queued for approval.' },
  { name: 'AI Clone & Creative', status: 'Queued', score: '81%', detail: 'Creative draft waiting for approval.' },
  { name: 'Video Production', status: 'Ready', score: '86%', detail: 'Scene edit schedule validated.' },
  { name: 'Publishing & Scheduling', status: 'Awaiting approval', score: '74%', detail: 'Publishing plan prepared for legal sign-off.' },
];

export const workflowSteps = [
  { title: 'Creator setup', progress: 'Complete', time: '09:00 AM' },
  { title: 'Trend research', progress: 'Complete', time: '09:12 AM' },
  { title: 'Competitor analysis', progress: 'In review', time: '09:28 AM' },
  { title: 'Script drafting', progress: 'Queued', time: '09:46 AM' },
  { title: 'Approval rhythm', progress: 'Pending', time: '10:10 AM' },
];

export const sampleCreator = {
  name: 'Alicia Moreno',
  brand_name: 'Alicia Creates',
  niche: 'Personal brand growth',
  email: 'hello@aliciacreates.com',
  platform_focus: 'Instagram',
  bio: 'Story-led marketing educator helping creators build a confident digital presence.',
  website: 'https://aliciacreates.com',
  approved_for_publication: true,
  authorized_for_avatar_use: false,
};
