import { Network, Server, CheckCircle, XCircle, AlertTriangle, RefreshCw, Plus, Trash2, Settings2 } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

// Mock node data - TODO: Replace with real API
const mockNodes = [
  {
    id: 'node-1',
    name: 'Primary Node',
    address: 'localhost:8080',
    status: 'online' as const,
    role: 'primary',
    load: 45,
    connections: 12,
    uptime: '7d 14h',
  },
  {
    id: 'node-2',
    name: 'Worker Node 1',
    address: '192.168.1.101:8080',
    status: 'online' as const,
    role: 'worker',
    load: 32,
    connections: 8,
    uptime: '5d 2h',
  },
  {
    id: 'node-3',
    name: 'Worker Node 2',
    address: '192.168.1.102:8080',
    status: 'offline' as const,
    role: 'worker',
    load: 0,
    connections: 0,
    uptime: '-',
  },
]

interface Node {
  id: string
  name: string
  address: string
  status: 'online' | 'offline' | 'degraded'
  role: string
  load: number
  connections: number
  uptime: string
}

function NodeCard({ 
  node, 
  onConfigure, 
  onRemove 
}: { 
  node: Node
  onConfigure?: () => void
  onRemove?: () => void
}) {
  const getStatusIcon = () => {
    switch (node.status) {
      case 'online':
        return <CheckCircle size={16} className="text-giga-success" />
      case 'offline':
        return <XCircle size={16} className="text-giga-error" />
      case 'degraded':
        return <AlertTriangle size={16} className="text-giga-warning" />
    }
  }

  const getStatusColor = () => {
    switch (node.status) {
      case 'online':
        return 'border-giga-success/30'
      case 'offline':
        return 'border-giga-error/30 opacity-60'
      case 'degraded':
        return 'border-giga-warning/30'
    }
  }

  return (
    <div className={cn('card p-4 border', getStatusColor())}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            {getStatusIcon()}
            <h4 className="font-medium text-white">{node.name}</h4>
            <span className={cn(
              'px-1.5 py-0.5 text-[10px] font-medium rounded capitalize',
              node.role === 'primary' ? 'bg-purple-500/20 text-purple-400' : 'bg-gray-500/20 text-gray-400'
            )}>
              {node.role}
            </span>
          </div>
          
          <p className="text-sm text-gray-400 font-mono mb-3">{node.address}</p>

          {node.status === 'online' && (
            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <p className="text-gray-500">Load</p>
                <div className="flex items-center gap-2 mt-1">
                  <div className="flex-1 h-1.5 bg-giga-dark rounded-full overflow-hidden">
                    <div 
                      className={cn(
                        'h-full rounded-full',
                        node.load < 50 ? 'bg-giga-success' : node.load < 80 ? 'bg-giga-warning' : 'bg-giga-error'
                      )}
                      style={{ width: `${node.load}%` }}
                    />
                  </div>
                  <span className="text-gray-300">{node.load}%</span>
                </div>
              </div>
              <div>
                <p className="text-gray-500">Connections</p>
                <p className="text-gray-300 mt-1">{node.connections}</p>
              </div>
              <div>
                <p className="text-gray-500">Uptime</p>
                <p className="text-gray-300 mt-1">{node.uptime}</p>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1">
          <button 
            onClick={onConfigure}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-giga-hover transition-colors"
            title="Configure"
          >
            <Settings2 size={16} />
          </button>
          {node.role !== 'primary' && (
            <button 
              onClick={onRemove}
              className="p-2 rounded-lg text-gray-400 hover:text-giga-error hover:bg-giga-error/10 transition-colors"
              title="Remove"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function AddNodeModal({ 
  isOpen, 
  onClose,
  onAdd 
}: { 
  isOpen: boolean
  onClose: () => void
  onAdd: (node: Partial<Node>) => void
}) {
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-giga-card border border-giga-border rounded-xl p-6 w-full max-w-md mx-4">
        <h3 className="text-lg font-bold text-white mb-4">Add Node</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white placeholder-gray-500 focus:border-giga-accent focus:outline-none"
              placeholder="Worker Node 3"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Address</label>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full px-3 py-2 bg-giga-dark border border-giga-border rounded-lg text-white font-mono placeholder-gray-500 focus:border-giga-accent focus:outline-none"
              placeholder="192.168.1.103:8080"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button 
            onClick={() => {
              onAdd({ name, address, role: 'worker', status: 'offline' })
              onClose()
              setName('')
              setAddress('')
            }}
            disabled={!name.trim() || !address.trim()}
            className="btn-primary disabled:opacity-50"
          >
            Add Node
          </button>
        </div>
      </div>
    </div>
  )
}

export function NodesPanel() {
  const [showAddModal, setShowAddModal] = useState(false)

  const onlineNodes = mockNodes.filter(n => n.status === 'online')
  const offlineNodes = mockNodes.filter(n => n.status !== 'online')

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-teal-500/20 flex items-center justify-center">
              <Network size={20} className="text-teal-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Nodes</h2>
              <p className="text-sm text-gray-400">
                {onlineNodes.length} online, {offlineNodes.length} offline
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-secondary flex items-center gap-2">
              <RefreshCw size={16} />
              <span>Refresh</span>
            </button>
            <button 
              onClick={() => setShowAddModal(true)}
              className="btn-primary flex items-center gap-2"
            >
              <Plus size={16} />
              <span>Add Node</span>
            </button>
          </div>
        </div>

        {/* Cluster Overview */}
        <div className="card p-4">
          <h3 className="font-medium text-white mb-4 flex items-center gap-2">
            <Server size={16} className="text-giga-accent" />
            Cluster Overview
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-500">Total Nodes</p>
              <p className="text-2xl font-bold text-white">{mockNodes.length}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Online</p>
              <p className="text-2xl font-bold text-giga-success">{onlineNodes.length}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Total Connections</p>
              <p className="text-2xl font-bold text-white">
                {mockNodes.reduce((acc, n) => acc + n.connections, 0)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Avg Load</p>
              <p className="text-2xl font-bold text-white">
                {Math.round(onlineNodes.reduce((acc, n) => acc + n.load, 0) / (onlineNodes.length || 1))}%
              </p>
            </div>
          </div>
        </div>

        {/* Node List */}
        <div className="space-y-3">
          {mockNodes.map((node) => (
            <NodeCard
              key={node.id}
              node={node}
              onConfigure={() => console.log('Configure', node.id)}
              onRemove={() => console.log('Remove', node.id)}
            />
          ))}
        </div>
      </div>

      <AddNodeModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdd={(node) => console.log('Add node:', node)}
      />
    </div>
  )
}
