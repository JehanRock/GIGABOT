import { Clock, Play, Pause, Trash2, Plus, History, CheckCircle, XCircle, Calendar } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

// Mock data - TODO: Replace with real API
const mockCronJobs = [
  {
    id: 'cron-1',
    name: 'Daily Summary',
    schedule: '0 9 * * *',
    humanReadable: 'Every day at 9:00 AM',
    enabled: true,
    lastRun: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    lastStatus: 'success' as const,
    nextRun: new Date(Date.now() + 1000 * 60 * 60 * 12).toISOString(),
    task: 'Generate and send daily activity summary',
  },
  {
    id: 'cron-2',
    name: 'Weekly Backup',
    schedule: '0 2 * * 0',
    humanReadable: 'Every Sunday at 2:00 AM',
    enabled: true,
    lastRun: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(),
    lastStatus: 'success' as const,
    nextRun: new Date(Date.now() + 1000 * 60 * 60 * 24 * 4).toISOString(),
    task: 'Backup memory and configuration',
  },
  {
    id: 'cron-3',
    name: 'Health Check',
    schedule: '*/30 * * * *',
    humanReadable: 'Every 30 minutes',
    enabled: false,
    lastRun: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    lastStatus: 'error' as const,
    nextRun: null,
    task: 'Check system health and report issues',
  },
]

const mockHistory = [
  { id: 'h1', jobId: 'cron-1', jobName: 'Daily Summary', time: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), status: 'success' as const, duration: '2.3s' },
  { id: 'h2', jobId: 'cron-3', jobName: 'Health Check', time: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), status: 'error' as const, duration: '0.5s', error: 'Connection timeout' },
  { id: 'h3', jobId: 'cron-2', jobName: 'Weekly Backup', time: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(), status: 'success' as const, duration: '45.2s' },
]

interface CronJob {
  id: string
  name: string
  schedule: string
  humanReadable: string
  enabled: boolean
  lastRun: string | null
  lastStatus: 'success' | 'error' | 'running' | null
  nextRun: string | null
  task: string
}

function CronJobCard({ 
  job, 
  onToggle, 
  onRun, 
  onDelete 
}: { 
  job: CronJob
  onToggle?: () => void
  onRun?: () => void
  onDelete?: () => void
}) {
  const formatDate = (date: string | null) => {
    if (!date) return 'N/A'
    return new Date(date).toLocaleString()
  }

  return (
    <div className={cn('card p-4', !job.enabled && 'opacity-60')}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-medium text-white">{job.name}</h4>
            {job.lastStatus === 'success' && (
              <CheckCircle size={14} className="text-giga-success" />
            )}
            {job.lastStatus === 'error' && (
              <XCircle size={14} className="text-giga-error" />
            )}
          </div>
          <p className="text-sm text-gray-400 mb-2">{job.task}</p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
            <span className="font-mono bg-giga-dark px-2 py-0.5 rounded">{job.schedule}</span>
            <span>{job.humanReadable}</span>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500 mt-2">
            <span>Last: {formatDate(job.lastRun)}</span>
            {job.nextRun && <span>Next: {formatDate(job.nextRun)}</span>}
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button 
            onClick={onRun}
            className="p-2 rounded-lg text-gray-400 hover:text-giga-accent hover:bg-giga-accent/10 transition-colors"
            title="Run Now"
          >
            <Play size={16} />
          </button>
          <button 
            onClick={onToggle}
            className={cn(
              'p-2 rounded-lg transition-colors',
              job.enabled 
                ? 'text-giga-success hover:text-giga-warning hover:bg-giga-warning/10' 
                : 'text-gray-500 hover:text-giga-success hover:bg-giga-success/10'
            )}
            title={job.enabled ? 'Disable' : 'Enable'}
          >
            {job.enabled ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <button 
            onClick={onDelete}
            className="p-2 rounded-lg text-gray-400 hover:text-giga-error hover:bg-giga-error/10 transition-colors"
            title="Delete"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

function AddCronModal({ 
  isOpen, 
  onClose,
  onAdd 
}: { 
  isOpen: boolean
  onClose: () => void
  onAdd: (job: Partial<CronJob>) => void
}) {
  const [name, setName] = useState('')
  const [schedule, setSchedule] = useState('')
  const [task, setTask] = useState('')

  const presets = [
    { label: 'Every hour', value: '0 * * * *' },
    { label: 'Every day at 9 AM', value: '0 9 * * *' },
    { label: 'Every Monday', value: '0 9 * * 1' },
    { label: 'Every 30 min', value: '*/30 * * * *' },
  ]

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-giga-card border border-giga-border rounded-xl p-6 w-full max-w-md mx-4">
        <h3 className="text-lg font-bold text-white mb-4">Add Cron Job</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white placeholder-gray-500 focus:border-giga-accent focus:outline-none"
              placeholder="Job name..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Schedule (cron)</label>
            <input
              value={schedule}
              onChange={(e) => setSchedule(e.target.value)}
              className="w-full px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white font-mono placeholder-gray-500 focus:border-giga-accent focus:outline-none"
              placeholder="0 9 * * *"
            />
            <div className="flex flex-wrap gap-2 mt-2">
              {presets.map((preset) => (
                <button
                  key={preset.value}
                  onClick={() => setSchedule(preset.value)}
                  className="px-2 py-1 text-xs bg-giga-dark border border-giga-border rounded text-gray-400 hover:text-white hover:border-giga-accent transition-colors"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Task</label>
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              className="w-full px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white placeholder-gray-500 focus:border-giga-accent focus:outline-none resize-none"
              rows={3}
              placeholder="What should this job do..."
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button 
            onClick={() => {
              onAdd({ name, schedule, task, enabled: true })
              onClose()
              setName('')
              setSchedule('')
              setTask('')
            }}
            disabled={!name.trim() || !schedule.trim() || !task.trim()}
            className="btn-primary disabled:opacity-50"
          >
            Add Job
          </button>
        </div>
      </div>
    </div>
  )
}

export function CronPanel() {
  const [showAddModal, setShowAddModal] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center">
              <Clock size={20} className="text-cyan-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Cron Jobs</h2>
              <p className="text-sm text-gray-400">
                {mockCronJobs.filter(j => j.enabled).length} active jobs
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button 
              onClick={() => setShowHistory(!showHistory)}
              className={cn(
                'btn-secondary flex items-center gap-2',
                showHistory && 'bg-giga-accent/20 border-giga-accent'
              )}
            >
              <History size={16} />
              <span>History</span>
            </button>
            <button 
              onClick={() => setShowAddModal(true)}
              className="btn-primary flex items-center gap-2"
            >
              <Plus size={16} />
              <span>Add Job</span>
            </button>
          </div>
        </div>

        {/* History Panel */}
        {showHistory && (
          <div className="card p-4">
            <h3 className="font-medium text-white mb-4 flex items-center gap-2">
              <History size={16} className="text-giga-accent" />
              Execution History
            </h3>
            <div className="space-y-2">
              {mockHistory.map((entry) => (
                <div key={entry.id} className="flex items-center justify-between p-2 rounded-lg bg-giga-dark">
                  <div className="flex items-center gap-3">
                    {entry.status === 'success' ? (
                      <CheckCircle size={14} className="text-giga-success" />
                    ) : (
                      <XCircle size={14} className="text-giga-error" />
                    )}
                    <span className="text-sm text-gray-300">{entry.jobName}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>{entry.duration}</span>
                    <span>{new Date(entry.time).toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Jobs List */}
        <div className="space-y-3">
          {mockCronJobs.map((job) => (
            <CronJobCard
              key={job.id}
              job={job}
              onToggle={() => console.log('Toggle', job.id)}
              onRun={() => console.log('Run', job.id)}
              onDelete={() => console.log('Delete', job.id)}
            />
          ))}
        </div>
      </div>

      <AddCronModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdd={(job) => console.log('Add job:', job)}
      />
    </div>
  )
}
