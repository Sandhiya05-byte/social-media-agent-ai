import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  ArrowUpRight,
  CheckCheck,
  CirclePlay,
  Clock3,
  Sparkles,
  TrendingUp,
  Users,
} from 'lucide-react';
import { motion } from 'framer-motion';

import { Sidebar } from './components/Sidebar';
import { TopNav } from './components/TopNav';
import {
  API_BASE_URL,
  createCreatorProfile,
  fetchCreatorProfiles,
  fetchDashboard,
  runResearchWorkflow,
} from './api/client';
import {
  approveContent,
  cancelSchedule,
  createContentItem,
  fetchContentItems,
  rejectContent,
  requestChanges,
  rescheduleContent,
  scheduleContent,
  validateContent,
  addWorkflowContentToReview,
} from './api/contentClient';
import { generateCreative } from './api/creativeClient';
import {
  approveWorkflow,
  fetchWorkflowStatus,
  rejectWorkflow,
  requestWorkflowChanges,
  resumeWorkflow,
  runWorkflow,
} from './api/orchestrationClient';
import { agentStatus, sampleCreator, sidebarItems, workflowSteps } from './data/demoData';
import { ServiceHealthPanel } from './components/ServiceHealthPanel';

const CALENDAR_DAYS = Array.from({ length: 7 }, (_, index) => {
  const date = new Date();
  date.setDate(date.getDate() + index);
  return date;
});

function parseUtcDate(value) {
  if (!value) {
    return null;
  }
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function toLocalInputValue(value) {
  const date = value instanceof Date ? value : parseUtcDate(value);
  if (!date) {
    return '';
  }
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

const defaultForm = {
  name: sampleCreator.name,
  brand_name: sampleCreator.brand_name,
  niche: sampleCreator.niche,
  email: sampleCreator.email,
  platform_focus: sampleCreator.platform_focus,
  bio: sampleCreator.bio,
  website: sampleCreator.website,
  approved_for_publication: sampleCreator.approved_for_publication,
  authorized_for_avatar_use: sampleCreator.authorized_for_avatar_use,
};

function App() {
  const [formData, setFormData] = useState(defaultForm);
  const [creator, setCreator] = useState(sampleCreator);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [metrics, setMetrics] = useState({ totalPosts: 24, approved: 14, scheduled: 9, pipeline: 6 });
  const [researchForm, setResearchForm] = useState({
    niche: 'creator growth',
    competitor_urls: 'https://www.youtube.com/results?search_query=creator+growth,https://www.linkedin.com/company/instagram',
    creator_writing_samples: 'I help creators build simple systems that create repeatable momentum.,The best content strategy is not louder. It is clearer and more consistent.',
    rss_sources: 'https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml,https://www.theverge.com/rss/index.xml',
  });
  const [researchResult, setResearchResult] = useState(null);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchError, setResearchError] = useState('');
  const [workflowForm, setWorkflowForm] = useState({
    campaign_topic: 'Creator growth systems',
    target_audience: 'new creators',
    platforms: 'Instagram,YouTube',
    campaign_objective: 'Build clear educational content without overproduction.',
    content_type: 'short-form',
  });
  const [workflowResult, setWorkflowResult] = useState(null);
  const [workflowHistory, setWorkflowHistory] = useState([]);
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [workflowError, setWorkflowError] = useState('');
  const [creativeForm, setCreativeForm] = useState({
    title: 'Creator Growth Playbook',
    platform: 'Instagram',
    content: 'A simple system to grow without chasing trends.',
    script: 'Use a repeatable framework to make clear, consistent content.',
    captions: 'Hook, Explain, Framework, CTA',
  });
  const [creativeResult, setCreativeResult] = useState(null);
  const [creativeLoading, setCreativeLoading] = useState(false);
  const [creativeError, setCreativeError] = useState('');
  const [contentForm, setContentForm] = useState({
    title: 'Creator Growth Playbook',
    platform: 'Instagram',
    content: 'A simple system to grow without chasing trends.',
    script: 'Use a repeatable framework to make clear, consistent content.',
    captions: 'Hook, Explain, Framework, CTA',
    media_path: '/generated/creative/instagram_creator_growth_playbook.png',
  });
  const [contentValidation, setContentValidation] = useState(null);
  const [validationError, setValidationError] = useState('');
  const [contentQueue, setContentQueue] = useState([]);
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [scheduleContentId, setScheduleContentId] = useState('');
  const [sendToReviewLoading, setSendToReviewLoading] = useState(false);
  const [scheduleView, setScheduleView] = useState('weekly');
  const [scheduleDateTime, setScheduleDateTime] = useState(() =>
    toLocalInputValue(new Date(Date.now() + 60 * 60 * 1000)),
  );

  useEffect(() => {
    const loadCreator = async () => {
      try {
        const profiles = await fetchCreatorProfiles();
        if (profiles.length > 0) {
          const latest = profiles[0];
          setCreator(latest);
          setFormData({
            name: latest.name,
            brand_name: latest.brand_name,
            niche: latest.niche,
            email: latest.email,
            platform_focus: latest.platform_focus,
            bio: latest.bio || '',
            website: latest.website || '',
            approved_for_publication: latest.approved_for_publication,
            authorized_for_avatar_use: latest.authorized_for_avatar_use,
          });
        }
      } catch {
        setCreator(sampleCreator);
      }

      try {
        const dashboard = await fetchDashboard();
        setMetrics({
          totalPosts: dashboard.content?.total ?? 0,
          approved: (dashboard.content?.by_status?.Approved || 0) + (dashboard.content?.by_status?.Scheduled || 0),
          scheduled: dashboard.content?.scheduled ?? 0,
          pipeline:
            (dashboard.content?.by_status?.['Awaiting Approval'] || 0) +
            (dashboard.content?.by_status?.['Validation Failed'] || 0),
        });
      } catch {
        setMetrics({ totalPosts: 0, approved: 0, scheduled: 0, pipeline: 0 });
      }

      try {
        const items = await fetchContentItems();
        setContentQueue(items);
      } catch {
        setContentQueue([]);
      }
    };

    loadCreator();
  }, []);

  useEffect(() => {
    if (!workflowResult?.workflow_id) {
      return undefined;
    }

    const pollState = { cancelled: false, timer: null, inFlight: false };

    const terminalStatuses = new Set([
      'COMPLETED',
      'FAILED',
      'CANCELLED',
      'REJECTED',
      'SCHEDULED',
      'WAITING_FOR_APPROVAL',
      'APPROVED',
    ]);

    const stopPolling = () => {
      pollState.cancelled = true;
      if (pollState.timer) {
        clearInterval(pollState.timer);
        pollState.timer = null;
      }
    };

    const pollWorkflow = async () => {
      if (pollState.inFlight || pollState.cancelled) {
        return;
      }

      pollState.inFlight = true;

      try {
        const latest = await fetchWorkflowStatus(workflowResult.workflow_id);
        if (pollState.cancelled) {
          return;
        }

        const normalizedStatus = String(latest?.status ?? '').toUpperCase();
        if (terminalStatuses.has(normalizedStatus)) {
          stopPolling();
          setWorkflowResult((previous) => {
            if (!previous) {
              return previous;
            }

            return {
              ...previous,
              status: normalizedStatus,
              context: {
                ...(previous.context || {}),
                ...(latest.execution_summary ? { execution_summary: latest.execution_summary } : {}),
              },
            };
          });
          return;
        }

        setWorkflowResult((previous) => {
          if (!previous) {
            return previous;
          }

          return {
            ...previous,
            status: normalizedStatus,
            context: {
              ...(previous.context || {}),
              ...(latest.execution_summary ? { execution_summary: latest.execution_summary } : {}),
            },
          };
        });
      } catch (pollError) {
        const statusCode = pollError?.response?.status ?? pollError?.status;
        if (statusCode === 404) {
          stopPolling();
        }
      } finally {
        pollState.inFlight = false;
      }
    };

    pollWorkflow();
    pollState.timer = setInterval(pollWorkflow, 4000);

    return () => {
      stopPolling();
    };
  }, [workflowResult?.workflow_id]);

  const heroCards = useMemo(
    () => [
      { label: 'Pipeline health', value: metrics.pipeline > 0 ? `${metrics.pipeline} in review` : 'Idle', tone: 'violet' },
      { label: 'Content approvals', value: String(metrics.pendingApprovals ?? metrics.approved), tone: 'cyan' },
      { label: 'Ready to publish', value: String(metrics.scheduled), tone: 'emerald' },
    ],
    [metrics],
  );

  const handleInputChange = (event) => {
    const { name, value, type, checked } = event.target;
    setFormData((previous) => ({
      ...previous,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    setSuccessMessage('');

    try {
      const savedCreator = await createCreatorProfile(formData);
      setCreator(savedCreator);
      setSuccessMessage('Creator profile saved and synced with the backend.');
    } catch (submitError) {
      setError(submitError.message || 'Unable to save profile.');
    } finally {
      setLoading(false);
    }
  };

  const handleResearchInputChange = (event) => {
    const { name, value } = event.target;
    setResearchForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const handleResearchSubmit = async (event) => {
    event.preventDefault();
    setResearchLoading(true);
    setResearchError('');

    try {
      const payload = {
        niche: researchForm.niche,
        competitor_urls: researchForm.competitor_urls
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        creator_writing_samples: researchForm.creator_writing_samples
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        rss_sources: researchForm.rss_sources
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      };

      const result = await runResearchWorkflow(payload);
      setResearchResult(result);
    } catch (submitError) {
      setResearchError(submitError.message || 'Research workflow failed.');
    } finally {
      setResearchLoading(false);
    }
  };

  const handleWorkflowInputChange = (event) => {
    const { name, value } = event.target;
    setWorkflowForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const handleWorkflowSubmit = async (event) => {
    event.preventDefault();
    setWorkflowLoading(true);
    setWorkflowError('');

    try {
      const payload = {
        campaign_topic: workflowForm.campaign_topic,
        target_audience: workflowForm.target_audience,
        platforms: workflowForm.platforms
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        campaign_objective: workflowForm.campaign_objective,
        content_type: workflowForm.content_type,
        competitor_urls: researchResult?.competitor_observations
          ? researchResult.competitor_observations.map((item) => item.source_url || '').filter(Boolean)
          : [],
        rss_sources: researchResult?.agent_statuses
          ? researchResult.agent_statuses
              .flatMap((agent) => agent.source_urls || [])
              .filter(Boolean)
          : [],
        creator_writing_samples: researchForm.creator_writing_samples
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      };

      const result = await runWorkflow(payload);
      setWorkflowResult(result);
      setWorkflowHistory((previous) => [
        { workflow_id: result.workflow_id, status: result.status },
        ...previous.filter((item) => item.workflow_id !== result.workflow_id),
      ].slice(0, 5));

      // Clear stale defaults: the new campaign's own generated output
      // replaces any previous campaign's form values.
      const creative = result?.context?.creative_output || {};
      const video = result?.context?.video_output || {};
      setContentForm({
        title: creative.title || workflowForm.campaign_topic,
        platform: payload.platforms[0] || 'Instagram',
        content: creative.content || '',
        script: creative.script || '',
        captions: (creative.captions || []).join(', '),
        media_path: video.video_url || '',
      });
      await refreshQueue();
    } catch (submitError) {
      setWorkflowError(submitError.message || 'Workflow orchestration failed.');
    } finally {
      setWorkflowLoading(false);
    }
  };

  const handleWorkflowDecision = async (action) => {
    const workflowId = workflowResult?.workflow_id;
    if (!workflowId) {
      return;
    }

    setWorkflowLoading(true);
    setWorkflowError('');

    try {
      let result;
      if (action === 'approve') {
        await approveWorkflow(workflowId, {
          approved_by: 'creator',
          notes: 'Approved from the command center.',
        });
        result = await resumeWorkflow(workflowId);
      } else if (action === 'reject') {
        result = await rejectWorkflow(workflowId, {
          approved_by: 'creator',
          notes: 'Rejected from the command center.',
        });
      } else {
        result = await requestWorkflowChanges(workflowId, {
          approved_by: 'creator',
          notes: 'Changes requested from the command center.',
        });
      }

      if (result?.workflow_id) {
        setWorkflowResult(result);
        setWorkflowHistory((previous) =>
          previous.map((item) =>
            item.workflow_id === result.workflow_id ? { ...item, status: result.status } : item,
          ),
        );
      }
    } catch (decisionError) {
      setWorkflowError(decisionError.message || 'Workflow approval action failed.');
      try {
        const latest = await fetchWorkflowStatus(workflowId);
        setWorkflowResult((previous) =>
          previous
            ? {
                ...previous,
                status: latest.status,
                context: {
                  ...(previous.context || {}),
                  ...(latest.execution_summary
                    ? { execution_summary: latest.execution_summary }
                    : {}),
                },
              }
            : previous,
        );
      } catch (refreshError) {
        void refreshError;
      }
    } finally {
      setWorkflowLoading(false);
    }
  };

  const handleCreativeInputChange = (event) => {
    const { name, value } = event.target;
    setCreativeForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const handleCreativeSubmit = async (event) => {
    event.preventDefault();
    setCreativeLoading(true);
    setCreativeError('');

    try {
      const payload = {
        title: creativeForm.title,
        platform: creativeForm.platform,
        content: creativeForm.content,
        script: creativeForm.script,
        captions: creativeForm.captions
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      };

      const result = await generateCreative(payload);
      setCreativeResult(result);
      const videoUrl = result?.video?.video_url || '';
      setContentForm({
        title: result?.creative?.title || creativeForm.title,
        platform: creativeForm.platform,
        content: result?.creative?.content || creativeForm.content,
        script: result?.creative?.script || creativeForm.script,
        captions: (result?.creative?.captions || []).join(', ') || creativeForm.captions,
        media_path: videoUrl,
      });
      if (!videoUrl) {
        setCreativeError('Video render failed - no MP4 was produced. Check the render error above.');
      }
    } catch (submitError) {
      setCreativeError(submitError.message || 'Creative generation failed.');
    } finally {
      setCreativeLoading(false);
    }
  };

  const refreshQueue = async () => {
    try {
      const items = await fetchContentItems();
      setContentQueue(items);
      const schedulable = items.find(
        (item) => item.status === 'Approved' || item.status === 'Scheduled',
      );
      if (schedulable) {
        setScheduleContentId(String(schedulable.id));
      }
    } catch {
      setContentQueue([]);
    }
  };

  const handleSendWorkflowToReview = async () => {
    const workflowId = workflowResult?.workflow_id;
    if (!workflowId) {
      return;
    }
    setSendToReviewLoading(true);
    setValidationError('');
    try {
      await addWorkflowContentToReview(workflowId);
      await refreshQueue();
    } catch (reviewError) {
      setValidationError(reviewError.message || 'Unable to send workflow content to review.');
    } finally {
      setSendToReviewLoading(false);
    }
  };

  const handleContentInputChange = (event) => {
    const { name, value } = event.target;
    setContentForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const handleValidationSubmit = async (event) => {
    event.preventDefault();
    setValidationError('');
    try {
      const payload = {
        title: contentForm.title,
        platform: contentForm.platform,
        content: contentForm.content,
        script: contentForm.script,
        captions: contentForm.captions
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        media_path: contentForm.media_path,
      };
      const result = await validateContent(payload);
      setContentValidation(result);
    } catch (submitError) {
      setValidationError(submitError.message || 'Validation failed.');
    }
  };

  const handleCreateForApproval = async (event) => {
    event.preventDefault();
    setValidationError('');
    try {
      const payload = {
        title: contentForm.title,
        platform: contentForm.platform,
        content: contentForm.content,
        script: contentForm.script,
        captions: contentForm.captions
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        media_path: contentForm.media_path,
      };
      const created = await createContentItem(payload);
      await refreshQueue();
      setContentValidation(null);
      setValidationError('');
      return created;
    } catch (submitError) {
      setValidationError(submitError.message || 'Unable to add content to the review queue.');
    }
  };

  const handleApprovalAction = async (contentId, action, notes = '') => {
    setApprovalLoading(true);
    try {
      if (action === 'approve') {
        await approveContent(contentId, notes, 'creator');
      } else if (action === 'reject') {
        await rejectContent(contentId, notes);
      } else if (action === 'changes') {
        await requestChanges(contentId, notes);
      }
      await refreshQueue();
    } catch (approvalError) {
      setValidationError(approvalError.message || 'Approval action failed.');
    } finally {
      setApprovalLoading(false);
    }
  };

  const handleScheduleAction = async (event) => {
    event.preventDefault();
    setValidationError('');

    if (!scheduleContentId) {
      setValidationError('Pick an approved item to schedule.');
      return;
    }

    try {
      const selectedItem = contentQueue.find(
        (item) => String(item.id) === String(scheduleContentId),
      );
      const scheduledFor = new Date(scheduleDateTime).toISOString();

      if (selectedItem?.status === 'Scheduled') {
        await rescheduleContent(scheduleContentId, scheduledFor);
      } else {
        await scheduleContent(scheduleContentId, scheduledFor);
      }
      await refreshQueue();
    } catch (submitError) {
      setValidationError(submitError.message || 'Scheduling failed.');
    }
  };

  const handleCancelSchedule = async (contentId) => {
    setValidationError('');
    try {
      await cancelSchedule(contentId);
      await refreshQueue();
    } catch (cancelError) {
      setValidationError(cancelError.message || 'Unable to cancel the schedule.');
    }
  };

  const workflowAgents = workflowResult?.context?.agent_records
    ? Object.entries(workflowResult.context.agent_records)
    : [];

  const calendarDays =
    scheduleView === 'daily' ? CALENDAR_DAYS.slice(0, 1) : CALENDAR_DAYS;

  const scheduledItems = contentQueue.filter((item) => item.status === 'Scheduled' && item.scheduled_for);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="flex min-h-screen">
        <Sidebar items={sidebarItems} />

        <main className="flex-1 overflow-hidden">
          <TopNav creatorName={creator.name} />

          <div className="space-y-6 p-4 md:p-6 xl:p-8">
            <section className="rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950 p-6 shadow-2xl shadow-slate-950/40">
              <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
                <div>
                  <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-violet-200">
                    <Sparkles size={14} />
                    Command center
                  </div>
                  <h2 className="text-3xl font-semibold text-white md:text-4xl">AI media operations for {creator.brand_name}</h2>
                  <p className="mt-2 max-w-2xl text-sm text-slate-300 md:text-base">
                    Monitor trend discovery, content production, review queues and approval readiness from one operating dashboard.
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <button type="button" className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm font-medium text-slate-100 hover:border-slate-500">
                    View workflow
                  </button>
                  <button type="button" className="rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-900/30 hover:brightness-110">
                    Launch approval review
                  </button>
                </div>
              </div>

              <div className="mt-6 grid gap-4 md:grid-cols-3">
                {heroCards.map((card) => (
                  <motion.div
                    key={card.label}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`rounded-2xl border p-4 ${
                      card.tone === 'violet'
                        ? 'border-violet-500/30 bg-violet-500/10'
                        : card.tone === 'cyan'
                          ? 'border-cyan-500/30 bg-cyan-500/10'
                          : 'border-emerald-500/30 bg-emerald-500/10'
                    }`}
                  >
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-300">{card.label}</p>
                    <div className="mt-3 flex items-end justify-between">
                      <span className="text-3xl font-semibold text-white">{card.value}</span>
                      <ArrowUpRight className="text-slate-200" size={18} />
                    </div>
                  </motion.div>
                ))}
              </div>
            </section>

            <ServiceHealthPanel />

            <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
              <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Agent control room</p>
                    <h3 className="mt-1 text-xl font-semibold text-white">Seven-agent operating status</h3>
                  </div>
                  <button type="button" className="rounded-full border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-slate-500">
                    Live overview
                  </button>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  {agentStatus.map((agent) => (
                    <div key={agent.name} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-sm font-medium text-slate-200">{agent.name}</p>
                          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-violet-300">{agent.status}</p>
                        </div>
                        <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs font-medium text-cyan-300">{agent.score}</span>
                      </div>
                      <p className="mt-3 text-sm text-slate-300">{agent.detail}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Workflow progress</p>
                <h3 className="mt-1 text-xl font-semibold text-white">Lifecycle snapshot</h3>

                <div className="mt-5 space-y-4">
                  {workflowSteps.map((step, index) => (
                    <div key={step.title} className="flex items-start gap-3">
                      <div className="flex flex-col items-center">
                        <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                          step.progress === 'Complete'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : step.progress === 'In review'
                              ? 'bg-violet-500/20 text-violet-300'
                              : step.progress === 'Queued'
                                ? 'bg-cyan-500/20 text-cyan-300'
                                : 'bg-slate-700 text-slate-300'
                        }`}>
                          {index + 1}
                        </div>
                        {index < workflowSteps.length - 1 && <div className="mt-2 h-8 w-px bg-slate-700" />}
                      </div>

                      <div className="flex-1 rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-medium text-slate-100">{step.title}</p>
                          <span className="text-xs text-slate-300">{step.progress}</span>
                        </div>
                        <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
                          <Clock3 size={12} />
                          {step.time}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
              <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Orchestration engine</p>
                  <h3 className="mt-1 text-xl font-semibold text-white">Campaign workflow monitor</h3>
                </div>
                <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.2em] text-cyan-300">
                  seven-agent mode
                </span>
              </div>

              <form onSubmit={handleWorkflowSubmit} className="grid gap-4 md:grid-cols-2">
                <label className="block text-sm text-slate-300">
                  <span className="mb-2 block">Campaign topic</span>
                  <input name="campaign_topic" value={workflowForm.campaign_topic} onChange={handleWorkflowInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                </label>

                <label className="block text-sm text-slate-300">
                  <span className="mb-2 block">Target audience</span>
                  <input name="target_audience" value={workflowForm.target_audience} onChange={handleWorkflowInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                </label>

                <label className="block text-sm text-slate-300 md:col-span-2">
                  <span className="mb-2 block">Platforms</span>
                  <input name="platforms" value={workflowForm.platforms} onChange={handleWorkflowInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                </label>

                <label className="block text-sm text-slate-300 md:col-span-2">
                  <span className="mb-2 block">Campaign objective</span>
                  <input name="campaign_objective" value={workflowForm.campaign_objective} onChange={handleWorkflowInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                </label>

                <label className="block text-sm text-slate-300">
                  <span className="mb-2 block">Content type</span>
                  <select name="content_type" value={workflowForm.content_type} onChange={handleWorkflowInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500">
                    <option value="short-form">Short-form</option>
                    <option value="carousel">Carousel</option>
                    <option value="long-form">Long-form</option>
                  </select>
                </label>

                <div className="flex items-end">
                  <button type="submit" disabled={workflowLoading} className="w-full rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-900/30 disabled:cursor-not-allowed disabled:opacity-60">
                    {workflowLoading ? 'Running workflow...' : 'Run orchestration'}
                  </button>
                </div>
              </form>

              {workflowError && <p className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{workflowError}</p>}

              {workflowResult && (
                <div className="mt-5 space-y-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Workflow status</p>
                      <h4 className="mt-1 text-lg font-semibold text-white">{workflowResult.status}</h4>
                    </div>
                    <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300">
                      ID #{workflowResult.workflow_id}
                    </span>
                  </div>

                  {['WAITING_FOR_APPROVAL', 'PENDING', 'APPROVED'].includes(
                    String(workflowResult.status || '').toUpperCase(),
                  ) && (
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleWorkflowDecision('approve')}
                        disabled={workflowLoading}
                        className="rounded-lg bg-emerald-500/20 px-3 py-1.5 text-xs font-medium text-emerald-200 disabled:opacity-50"
                      >
                        {workflowLoading ? 'Working...' : 'Approve & run publishing agent'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleWorkflowDecision('changes')}
                        disabled={workflowLoading}
                        className="rounded-lg bg-amber-500/20 px-3 py-1.5 text-xs font-medium text-amber-200 disabled:opacity-50"
                      >
                        Request changes
                      </button>
                      <button
                        type="button"
                        onClick={() => handleWorkflowDecision('reject')}
                        disabled={workflowLoading}
                        className="rounded-lg bg-red-500/20 px-3 py-1.5 text-xs font-medium text-red-200 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  )}

                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-xl border border-slate-800 bg-slate-900 p-3">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Platform(s)</p>
                      <p className="mt-2 text-sm text-slate-100">{workflowResult.context?.platforms?.join(', ') || 'Not set'}</p>
                    </div>
                    <div className="rounded-xl border border-slate-800 bg-slate-900 p-3">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Approval</p>
                      <p className="mt-2 text-sm text-slate-100">{workflowResult.context?.approval_status || 'PENDING'}</p>
                    </div>
                    <div className="rounded-xl border border-slate-800 bg-slate-900 p-3">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Agents run</p>
                      <p className="mt-2 text-sm text-slate-100">{workflowAgents.length}</p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    {workflowAgents.map(([name, agent]) => (
                      <div key={name} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-sm">
                        <span className="text-slate-200">{name}</span>
                        <span className={`rounded-full px-2 py-1 text-[10px] font-medium uppercase tracking-[0.18em] ${agent.status === 'completed' ? 'bg-emerald-500/10 text-emerald-300' : 'bg-violet-500/10 text-violet-300'}`}>
                          {agent.status}
                        </span>
                      </div>
                    ))}
                  </div>

                  {workflowResult?.workflow_id && (
                    <button
                      type="button"
                      onClick={handleSendWorkflowToReview}
                      disabled={workflowLoading || sendToReviewLoading}
                      className="w-full rounded-xl border border-cyan-500/40 bg-cyan-500/10 px-4 py-2.5 text-sm font-semibold text-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {sendToReviewLoading ? 'Adding to review...' : 'Send generated content to Content Studio review'}
                    </button>
                  )}

                  {(() => {
                    const video = workflowResult?.context?.video_output || {};
                    if (!video.video_url && !video.render_error) return null;
                    return (
                      <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Generated video</p>
                        {video.video_url && video.video_format === 'mp4' ? (
                          <video src={`${API_BASE_URL}${video.video_url}`} controls playsInline className="mt-2 w-full rounded-xl border border-slate-700 bg-black" />
                        ) : video.video_url ? (
                          <p className="mt-2 text-sm text-amber-200">Offline fallback render (GIF, no sound) — MP4 rendering failed.</p>
                        ) : (
                          <p className="mt-2 text-sm text-red-200">Video generation failed: {video.render_error || video.tts_error}</p>
                        )}
                        {video.duration_seconds != null && (
                          <p className="mt-2 text-xs text-slate-300">
                            {Math.round(video.duration_seconds)}s · {video.video_width}x{video.video_height} · audio {video.audio_enabled ? 'on' : 'off'} · engine {video.render_engine}
                          </p>
                        )}
                        {(() => {
                          const creative = workflowResult?.context?.creative_output || {};
                          const gen = creative.generation_source || workflowResult?.context?.agent_records?.['AI Clone and Creative Agent']?.generation_source;
                          return gen ? (
                            <p className={`mt-1 text-xs ${gen === 'ollama' ? 'text-emerald-300' : 'text-amber-300'}`}>
                              Generation source: {gen}{gen !== 'ollama' ? ' (template fallback)' : ' (local model)'}
                            </p>
                          ) : null;
                        })()}
                        {(() => {
                          const research = workflowResult?.context?.research_findings || {};
                          const sources = research.source_references || [];
                          if (!sources.length) return null;
                          return (
                            <details className="mt-2 rounded-xl border border-slate-800 bg-slate-900/60 p-2 text-xs text-slate-300">
                              <summary className="cursor-pointer text-slate-200">Research sources ({sources.length})</summary>
                              <ul className="mt-2 space-y-1">
                                {sources.slice(0, 8).map((s, i) => (
                                  <li key={i}>
                                    <a href={s.url} target="_blank" rel="noreferrer" className="text-cyan-300 underline">{(s.title || s.url || '').slice(0, 80)}</a>
                                    <span className="ml-2 text-slate-500">[{s.provider}]</span>
                                  </li>
                                ))}
                              </ul>
                            </details>
                          );
                        })()}
                      </div>
                    );
                  })()}
                </div>
              )}

              {workflowHistory.length > 0 && (
                <div className="mt-5 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Recent workflow history</p>
                  <div className="mt-3 space-y-2">
                    {workflowHistory.map((workflow) => (
                      <div key={workflow.workflow_id} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-sm">
                        <span className="text-slate-200">#{workflow.workflow_id}</span>
                        <span className={`rounded-full px-2 py-1 text-[10px] font-medium uppercase tracking-[0.18em] ${workflow.status === 'completed' ? 'bg-emerald-500/10 text-emerald-300' : 'bg-violet-500/10 text-violet-300'}`}>
                          {workflow.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>

            <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
              <form onSubmit={handleSubmit} className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Creator setup</p>
                    <h3 className="mt-1 text-xl font-semibold text-white">Profile & approvals</h3>
                  </div>
                  <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-300">
                    {creator.approved_for_publication ? 'Approved' : 'Awaiting approval'}
                  </span>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2 text-sm text-slate-300">
                    <span>Name</span>
                    <input name="name" value={formData.name} onChange={handleInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none ring-0 transition focus:border-violet-500" />
                  </label>

                  <label className="space-y-2 text-sm text-slate-300">
                    <span>Brand name</span>
                    <input name="brand_name" value={formData.brand_name} onChange={handleInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none ring-0 transition focus:border-violet-500" />
                  </label>

                  <label className="space-y-2 text-sm text-slate-300">
                    <span>Niche</span>
                    <input name="niche" value={formData.niche} onChange={handleInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none ring-0 transition focus:border-violet-500" />
                  </label>

                  <label className="space-y-2 text-sm text-slate-300">
                    <span>Primary platform</span>
                    <select name="platform_focus" value={formData.platform_focus} onChange={handleInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500">
                      <option>Instagram</option>
                      <option>YouTube</option>
                      <option>LinkedIn</option>
                    </select>
                  </label>

                  <label className="space-y-2 text-sm text-slate-300 md:col-span-2">
                    <span>Email</span>
                    <input name="email" type="email" value={formData.email} onChange={handleInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="space-y-2 text-sm text-slate-300 md:col-span-2">
                    <span>Website</span>
                    <input name="website" value={formData.website} onChange={handleInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="space-y-2 text-sm text-slate-300 md:col-span-2">
                    <span>Bio</span>
                    <textarea name="bio" value={formData.bio} onChange={handleInputChange} rows={4} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="flex items-center gap-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200">
                    <input type="checkbox" name="approved_for_publication" checked={formData.approved_for_publication} onChange={handleInputChange} className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-violet-500 focus:ring-violet-500" />
                    Approved for publication
                  </label>

                  <label className="flex items-center gap-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200">
                    <input type="checkbox" name="authorized_for_avatar_use" checked={formData.authorized_for_avatar_use} onChange={handleInputChange} className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-violet-500 focus:ring-violet-500" />
                    Authorized avatar use
                  </label>
                </div>

                {error && <p className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</p>}
                {successMessage && <p className="mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">{successMessage}</p>}

                <button type="submit" disabled={loading} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-900/30 disabled:cursor-not-allowed disabled:opacity-60">
                  {loading ? 'Saving...' : 'Save profile'}
                </button>
              </form>

              <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Research engine</p>
                <h3 className="mt-1 text-xl font-semibold text-white">Trend and competitor research</h3>

                <form onSubmit={handleResearchSubmit} className="mt-5 space-y-4">
                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Niche</span>
                    <input name="niche" value={researchForm.niche} onChange={handleResearchInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Competitor URLs</span>
                    <textarea name="competitor_urls" value={researchForm.competitor_urls} onChange={handleResearchInputChange} rows={3} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Creator writing samples</span>
                    <textarea name="creator_writing_samples" value={researchForm.creator_writing_samples} onChange={handleResearchInputChange} rows={3} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">RSS sources</span>
                    <textarea name="rss_sources" value={researchForm.rss_sources} onChange={handleResearchInputChange} rows={3} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  {researchError && <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{researchError}</p>}

                  <button type="submit" disabled={researchLoading} className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-cyan-950/40 disabled:cursor-not-allowed disabled:opacity-60">
                    {researchLoading ? 'Running workflow...' : 'Run research workflow'}
                  </button>
                </form>

                {researchResult && (
                  <div className="mt-5 space-y-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-violet-300">Execution state</p>
                    {researchResult.agent_statuses?.map((item) => (
                      <div key={item.agent} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
                        <span className="text-sm text-slate-200">{item.agent}</span>
                        <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-emerald-300">
                          {item.status}
                        </span>
                      </div>
                    ))}

                    {(() => {
                      const statuses = researchResult.provider_statuses || {};
                      const entries = Object.entries(statuses);
                      if (!entries.length) return null;
                      return (
                        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Research providers</p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {entries.map(([name, status]) => (
                              <span key={name} className={`rounded-full px-2 py-1 text-[10px] font-medium uppercase tracking-[0.16em] ${
                                status === 'ok' ? 'bg-emerald-500/10 text-emerald-300' : status === 'unconfigured' || status === 'unavailable' ? 'bg-slate-700 text-slate-300' : 'bg-amber-500/10 text-amber-300'
                              }`}>
                                {name}: {status}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })()}

                    {(() => {
                      const sources = researchResult.source_references || [];
                      if (!sources.length) return null;
                      return (
                        <details className="rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-xs text-slate-300">
                          <summary className="cursor-pointer text-slate-200">Research sources ({sources.length})</summary>
                          <ul className="mt-2 space-y-1">
                            {sources.slice(0, 10).map((s, i) => (
                              <li key={i}>
                                <a href={s.url} target="_blank" rel="noreferrer" className="text-cyan-300 underline">{(s.title || s.url || '').slice(0, 80)}</a>
                                <span className="ml-2 text-slate-500">[{s.provider}]</span>
                              </li>
                            ))}
                          </ul>
                        </details>
                      );
                    })()}

                    {(researchResult.provider_limitations || []).length > 0 && (
                      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
                        {researchResult.provider_limitations.slice(0, 4).map((lim, i) => (
                          <p key={i}>{lim}</p>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Performance snapshot</p>
                <h3 className="mt-1 text-xl font-semibold text-white">Platform readiness</h3>

                <div className="mt-5 space-y-4">
                  {[
                    { label: 'Instagram', value: '80%', border: 'border-violet-400', accent: 'bg-violet-500' },
                    { label: 'YouTube', value: '68%', border: 'border-cyan-400', accent: 'bg-cyan-500' },
                    { label: 'LinkedIn', value: '74%', border: 'border-emerald-400', accent: 'bg-emerald-500' },
                  ].map((platform) => (
                    <div key={platform.label}>
                      <div className="mb-2 flex items-center justify-between text-sm text-slate-200">
                        <span>{platform.label}</span>
                        <span>{platform.value}</span>
                      </div>
                      <div className="h-2.5 rounded-full bg-slate-800">
                        <div className={`h-2.5 rounded-full ${platform.accent}`} style={{ width: platform.value }} />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <div className="flex items-center gap-2 text-slate-300">
                      <TrendingUp size={16} className="text-violet-300" />
                      Reach trend score
                    </div>
                    <p className="mt-3 text-2xl font-semibold text-white">8.7/10</p>
                  </div>

                  <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <div className="flex items-center gap-2 text-slate-300">
                      <Users size={16} className="text-cyan-300" />
                      Audience fit
                    </div>
                    <p className="mt-3 text-2xl font-semibold text-white">86%</p>
                  </div>

                  <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 sm:col-span-2">
                    <div className="flex items-center gap-2 text-slate-300">
                      <CheckCheck size={16} className="text-emerald-300" />
                      Publication controls
                    </div>
                    <p className="mt-3 text-sm text-slate-300">
                      Approval gate enabled. No publication occurs without creator sign-off and public-source citation review.
                    </p>
                  </div>
                </div>
              </div>
            </section>

            {researchResult && (
              <section className="grid gap-6 xl:grid-cols-3">
                <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30 xl:col-span-1">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Ranked topics</p>
                  <h3 className="mt-1 text-xl font-semibold text-white">Trend suggestions</h3>
                  <div className="mt-4 space-y-3">
                    {researchResult.ranked_topic_suggestions?.map((topic, index) => (
                      <div key={`${topic.title}-${index}`} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-medium text-slate-100">#{index + 1} {topic.title}</p>
                          <span className="rounded-full bg-violet-500/10 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-violet-300">{topic.score}</span>
                        </div>
                        <p className="mt-2 text-xs text-slate-300">{topic.why_it_matters}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30 xl:col-span-1">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Gap analysis</p>
                  <h3 className="mt-1 text-xl font-semibold text-white">Content opportunities</h3>
                  <div className="mt-4 space-y-3">
                    {researchResult.content_gap_suggestions?.map((gap, index) => (
                      <div key={`${gap.title}-${index}`} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                        <p className="text-sm font-medium text-slate-100">{gap.title}</p>
                        <p className="mt-2 text-xs text-slate-300">{gap.why_it_matters}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30 xl:col-span-1">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Hooks</p>
                  <h3 className="mt-1 text-xl font-semibold text-white">Hook alternatives</h3>
                  <div className="mt-4 space-y-3">
                    {researchResult.hook_alternatives?.map((hook, index) => (
                      <div key={`${hook}-${index}`} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200">
                        {hook}
                      </div>
                    ))}
                  </div>
                </div>
              </section>
            )}

            {creativeResult && (
              <section className="grid gap-6 xl:grid-cols-2">
                <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Creative preview</p>
                  <h3 className="mt-1 text-xl font-semibold text-white">Branded media output</h3>
                  <img
                    src={creativeResult.creative?.preview_url ? `${API_BASE_URL}${creativeResult.creative.preview_url}` : ''}
                    alt="Generated creative preview"
                    className="mt-4 h-72 w-full rounded-2xl border border-slate-700 object-cover"
                  />
                  <p className="mt-3 text-sm text-slate-300">{creativeResult.creative?.limits}</p>
                </div>
                <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Video render</p>
                  <h3 className="mt-1 text-xl font-semibold text-white">Export details</h3>

                  {creativeResult.video?.video_url && creativeResult.video?.video_format === 'mp4' ? (
                    <video
                      key={creativeResult.video.video_url}
                      src={`${API_BASE_URL}${creativeResult.video.video_url}`}
                      controls
                      playsInline
                      className="mt-4 w-full rounded-2xl border border-slate-700 bg-black"
                    />
                  ) : creativeResult.video?.video_url ? (
                    <div className="mt-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                      <p className="font-medium">Offline fallback render (GIF, no sound)</p>
                      <p className="mt-1">MP4 rendering failed, so a silent animated preview was generated instead.</p>
                      <img
                        src={`${API_BASE_URL}${creativeResult.video.video_url}`}
                        alt="Offline animated preview"
                        className="mt-3 w-full rounded-xl border border-slate-700"
                      />
                    </div>
                  ) : (
                    <div className="mt-4 rounded-2xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                      <p className="font-medium">No video output was produced</p>
                      <p className="mt-1">{creativeResult.video?.render_error || creativeResult.video?.tts_error || 'Video rendering failed. Check the backend logs and try again.'}</p>
                    </div>
                  )}

                  {(creativeResult.video?.render_error || creativeResult.video?.tts_error) && (
                    <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
                      {creativeResult.video?.tts_error && <p>Narration failed: {creativeResult.video.tts_error}</p>}
                      {creativeResult.video?.render_error && <p>MP4 render failed: {creativeResult.video.render_error}</p>}
                    </div>
                  )}

                  {creativeResult.video?.thumbnail_url && (
                    <div className="mt-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Thumbnail</p>
                      <img
                        src={`${API_BASE_URL}${creativeResult.video.thumbnail_url}`}
                        alt="Generated video thumbnail"
                        className="mt-2 h-40 w-full rounded-2xl border border-slate-700 object-cover"
                      />
                    </div>
                  )}

                  <div className="mt-4 space-y-1.5 rounded-2xl border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-200">
                    {creativeResult.video?.duration_seconds != null && (
                      <p>Duration: {Math.round(creativeResult.video.duration_seconds)}s</p>
                    )}
                    {creativeResult.video?.video_width != null && (
                      <p>Resolution: {creativeResult.video.video_width}x{creativeResult.video.video_height}</p>
                    )}
                    <p>Audio narration: {creativeResult.video?.audio_enabled ? 'Enabled (offline TTS)' : 'Not available'}</p>
                    <p>Render engine: {creativeResult.video?.render_engine || 'unknown'}</p>
                    {creativeResult.video?.subtitle_url && (
                      <p>
                        Subtitles:{' '}
                        <a
                          href={`${API_BASE_URL}${creativeResult.video.subtitle_url}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-cyan-300 underline"
                        >
                          Download SRT
                        </a>
                      </p>
                    )}
                    {creativeResult.video?.script_sufficient === false && (
                      <p className="text-amber-200">Script is short for a 60-90s video - edit or regenerate it for a longer narration.</p>
                    )}
                    <p className="text-xs text-slate-400">{creativeResult.video?.limits}</p>
                  </div>
                </div>
              </section>
            )}

            <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
              <form onSubmit={handleCreativeSubmit} className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Creative studio</p>
                <h3 className="mt-1 text-xl font-semibold text-white">Branded image and short-form video</h3>

                <div className="mt-5 space-y-4">
                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Title</span>
                    <input name="title" value={creativeForm.title} onChange={handleCreativeInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Platform</span>
                    <select name="platform" value={creativeForm.platform} onChange={handleCreativeInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500">
                      <option>Instagram</option>
                      <option>YouTube</option>
                      <option>LinkedIn</option>
                    </select>
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Creative content</span>
                    <textarea name="content" value={creativeForm.content} onChange={handleCreativeInputChange} rows={3} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Narration / script</span>
                    <textarea name="script" value={creativeForm.script} onChange={handleCreativeInputChange} rows={3} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Captions</span>
                    <textarea name="captions" value={creativeForm.captions} onChange={handleCreativeInputChange} rows={2} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  {creativeError && <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{creativeError}</p>}

                  <button type="submit" disabled={creativeLoading} className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-950/40 disabled:cursor-not-allowed disabled:opacity-60">
                    {creativeLoading ? 'Rendering...' : 'Generate creative'}
                  </button>
                </div>
              </form>

              <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Safety controls</p>
                <h3 className="mt-1 text-xl font-semibold text-white">Avatar and media guardrails</h3>

                <div className="mt-5 space-y-4 text-sm text-slate-300">
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <p className="font-medium text-white">Authorized creator media</p>
                    <p className="mt-2">Upload only creator-authorized image assets before template use.</p>
                  </div>
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <p className="font-medium text-white">Synthetic media disclosure</p>
                    <p className="mt-2">Generated visuals are clearly marked as template-based synthetic media.</p>
                  </div>
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <p className="font-medium text-white">No unauthorized cloning</p>
                    <p className="mt-2">Face or voice cloning never activates without explicit creator authorization.</p>
                  </div>
                </div>
              </div>
            </section>

            <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
              <form onSubmit={handleValidationSubmit} className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Validation gate</p>
                <h3 className="mt-1 text-xl font-semibold text-white">Content review and approval</h3>

                <div className="mt-5 space-y-4">
                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Title</span>
                    <input name="title" value={contentForm.title} onChange={handleContentInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Platform</span>
                    <select name="platform" value={contentForm.platform} onChange={handleContentInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500">
                      <option>Instagram</option>
                      <option>YouTube</option>
                      <option>LinkedIn</option>
                    </select>
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Content</span>
                    <textarea name="content" value={contentForm.content} onChange={handleContentInputChange} rows={4} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Script</span>
                    <textarea name="script" value={contentForm.script} onChange={handleContentInputChange} rows={3} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Captions</span>
                    <textarea name="captions" value={contentForm.captions} onChange={handleContentInputChange} rows={2} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  <label className="block text-sm text-slate-300">
                    <span className="mb-2 block">Media path</span>
                    <input name="media_path" value={contentForm.media_path} onChange={handleContentInputChange} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                  </label>

                  {validationError && <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{validationError}</p>}

                  <div className="flex flex-wrap gap-3">
                    <button type="submit" className="rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-950/40">Validate</button>
                    <button type="button" onClick={handleCreateForApproval} className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm font-medium text-slate-100 hover:border-slate-500">Add to approval queue</button>
                  </div>
                </div>

                {contentValidation && (
                  <div className="mt-5 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs uppercase tracking-[0.2em] text-violet-300">Validation result</p>
                      <span className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-[0.18em] ${contentValidation.status === 'passed' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'}`}>
                        {contentValidation.status}
                      </span>
                    </div>

                    {contentValidation.errors.length > 0 && (
                      <div className="mt-3 space-y-2 text-sm text-red-200">
                        <p className="font-medium">Errors</p>
                        {contentValidation.errors.map((item) => (
                          <li key={item} className="list-inside list-disc">{item}</li>
                        ))}
                      </div>
                    )}

                    {contentValidation.warnings.length > 0 && (
                      <div className="mt-3 space-y-2 text-sm text-amber-200">
                        <p className="font-medium">Warnings</p>
                        {contentValidation.warnings.map((item) => (
                          <li key={item} className="list-inside list-disc">{item}</li>
                        ))}
                      </div>
                    )}

                    {contentValidation.platform_checks.length > 0 && (
                      <div className="mt-3 text-sm text-slate-300">
                        <p className="font-medium text-slate-200">Platform checks</p>
                        <ul className="mt-2 list-inside list-disc space-y-1">
                          {contentValidation.platform_checks.map((item) => <li key={item}>{item}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </form>

              <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Approval queue</p>
                <h3 className="mt-1 text-xl font-semibold text-white">Human review board</h3>

                {contentQueue.length === 0 ? (
                  <div className="mt-5 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 p-5 text-sm text-slate-300">
                    No content is in the review queue yet.
                  </div>
                ) : (
                  <div className="mt-5 space-y-3">
                    {contentQueue.map((item) => (
                      <div key={item.id} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium text-white">{item.title}</p>
                            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-violet-300">{item.platform} Â· {item.status}</p>
                          </div>
                          <span className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-200">{item.status}</span>
                        </div>

                        {item.media_url && item.media_url.toLowerCase().includes('.mp4') && (
                          <video
                            key={item.media_url}
                            src={`${API_BASE_URL}${item.media_url}`}
                            controls
                            playsInline
                            className="mt-3 w-full rounded-xl border border-slate-700 bg-black"
                          />
                        )}

                        {item.thumbnail_url && (
                          <img
                            src={`${API_BASE_URL}${item.thumbnail_url}`}
                            alt="Content thumbnail"
                            className="mt-3 h-32 w-full rounded-xl border border-slate-700 object-cover"
                          />
                        )}

                        <p className="mt-3 text-sm text-slate-200">{item.content}</p>
                        {item.script && (
                          <details className="mt-2 rounded-xl border border-slate-800 bg-slate-900/60 p-2 text-xs text-slate-300">
                            <summary className="cursor-pointer text-slate-200">Narration script</summary>
                            <p className="mt-2 whitespace-pre-wrap">{item.script}</p>
                          </details>
                        )}
                        {item.subtitle_url && (
                          <a
                            href={`${API_BASE_URL}${item.subtitle_url}`}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-2 inline-block text-xs text-cyan-300 underline"
                          >
                            View subtitles (SRT)
                          </a>
                        )}

                        {item.validation_errors?.length > 0 && (
                          <ul className="mt-3 list-inside list-disc text-sm text-red-200">
                            {item.validation_errors.map((error) => <li key={`${item.id}-${error}`}>{error}</li>)}
                          </ul>
                        )}

                        {item.validation_warnings?.length > 0 && (
                          <ul className="mt-2 list-inside list-disc text-sm text-amber-200">
                            {item.validation_warnings.map((warning) => <li key={`${item.id}-${warning}`}>{warning}</li>)}
                          </ul>
                        )}

                        <div className="mt-3 flex flex-wrap gap-2">
                          <button type="button" onClick={() => handleApprovalAction(item.id, 'approve')} disabled={approvalLoading} className="rounded-lg bg-emerald-500/20 px-3 py-1.5 text-xs font-medium text-emerald-200 disabled:opacity-50">Approve</button>
                          <button type="button" onClick={() => handleApprovalAction(item.id, 'reject')} disabled={approvalLoading} className="rounded-lg bg-red-500/20 px-3 py-1.5 text-xs font-medium text-red-200 disabled:opacity-50">Reject</button>
                          <button type="button" onClick={() => handleApprovalAction(item.id, 'changes')} disabled={approvalLoading} className="rounded-lg bg-amber-500/20 px-3 py-1.5 text-xs font-medium text-amber-200 disabled:opacity-50">Request changes</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-slate-950/30">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Publishing calendar</p>
                  <h3 className="mt-1 text-xl font-semibold text-white">Schedule and monitor delivery</h3>
                </div>

                <div className="flex gap-2">
                  <button type="button" onClick={() => setScheduleView('daily')} className={`rounded-lg px-3 py-1.5 text-xs font-medium ${scheduleView === 'daily' ? 'bg-violet-500/20 text-violet-200' : 'border border-slate-700 bg-slate-950 text-slate-200'}`}>
                    Daily
                  </button>
                  <button type="button" onClick={() => setScheduleView('weekly')} className={`rounded-lg px-3 py-1.5 text-xs font-medium ${scheduleView === 'weekly' ? 'bg-violet-500/20 text-violet-200' : 'border border-slate-700 bg-slate-950 text-slate-200'}`}>
                    Weekly
                  </button>
                </div>
              </div>

              <form onSubmit={handleScheduleAction} className="mt-5 flex flex-col gap-3 md:flex-row md:items-end">
                <label className="flex-1 text-sm text-slate-300">
                  <span className="mb-2 block">Approved content</span>
                  <select value={scheduleContentId} onChange={(event) => setScheduleContentId(event.target.value)} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500">
                    <option value="">Select item</option>
                    {contentQueue.filter((item) => item.status === 'Approved' || item.status === 'Scheduled').map((item) => (
                      <option key={item.id} value={item.id}>{item.title}</option>
                    ))}
                  </select>
                </label>

                <label className="flex-1 text-sm text-slate-300">
                  <span className="mb-2 block">Schedule time</span>
                  <input type="datetime-local" value={scheduleDateTime} onChange={(event) => setScheduleDateTime(event.target.value)} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-white outline-none transition focus:border-violet-500" />
                </label>

                <button type="submit" className="rounded-xl bg-gradient-to-r from-cyan-500 to-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-cyan-950/30">Schedule</button>
              </form>

              <div className={`mt-6 grid gap-4 ${scheduleView === 'daily' ? 'md:grid-cols-1' : 'md:grid-cols-7'}`}>
                {calendarDays.map((day) => {
                  const key = day.toISOString().slice(0, 10);
                  const itemsForDay = scheduledItems.filter((item) => {
                    if (!item.scheduled_for) return false;
                    const scheduledDate = parseUtcDate(item.scheduled_for);
                    return scheduledDate?.toISOString().slice(0, 10) === key;
                  });

                  return (
                    <div key={key} className="rounded-2xl border border-slate-800 bg-slate-950/50 p-3">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{day.toLocaleDateString('en-US', { weekday: 'short' })}</p>
                      <p className="mt-2 text-lg font-semibold text-white">{day.getDate()}</p>
                      <div className="mt-3 space-y-2">
                        {itemsForDay.length === 0 ? (
                          <p className="text-xs text-slate-500">No schedule</p>
                        ) : (
                          itemsForDay.map((item) => (
                            <div key={item.id} className="rounded-xl border border-violet-500/30 bg-violet-500/10 p-2 text-[11px] text-slate-100">
                              <p className="font-medium">{item.title}</p>
                              <p className="mt-1 text-violet-200">{item.platform}</p>
                              <div className="mt-2 flex gap-2">
                                <button type="button" onClick={() => { setScheduleContentId(String(item.id)); setScheduleDateTime(toLocalInputValue(item.scheduled_for)); }} className="rounded-md border border-slate-700 px-2 py-1 text-[10px] text-slate-200">Edit</button>
                                <button type="button" onClick={() => handleCancelSchedule(item.id)} className="rounded-md border border-red-500/40 px-2 py-1 text-[10px] text-red-200">Cancel</button>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="grid gap-6 md:grid-cols-4">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
                <div className="flex items-center gap-2 text-slate-300">
                  <Activity size={16} className="text-violet-300" />
                  Total posts
                </div>
                <p className="mt-3 text-3xl font-semibold text-white">{metrics.totalPosts}</p>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
                <div className="flex items-center gap-2 text-slate-300">
                  <CheckCheck size={16} className="text-emerald-300" />
                  Approved
                </div>
                <p className="mt-3 text-3xl font-semibold text-white">{metrics.approved}</p>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
                <div className="flex items-center gap-2 text-slate-300">
                  <CirclePlay size={16} className="text-cyan-300" />
                  Scheduled
                </div>
                <p className="mt-3 text-3xl font-semibold text-white">{metrics.scheduled}</p>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
                <div className="flex items-center gap-2 text-slate-300">
                  <Sparkles size={16} className="text-amber-300" />
                  In pipeline
                </div>
                <p className="mt-3 text-3xl font-semibold text-white">{metrics.pipeline}</p>
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
