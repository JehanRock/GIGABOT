import { useMemo } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table'
import { useState } from 'react'
import { 
  ChevronUp, 
  ChevronDown, 
  ChevronLeft, 
  ChevronRight,
  MessageSquare,
  MoreHorizontal
} from 'lucide-react'
import { useSessions } from '@/hooks/useSessions'
import { cn, formatRelativeTime, getChannelColor, getChannelInitials } from '@/lib/utils'
import type { Session } from '@/types'

interface SessionTableProps {
  searchQuery: string
  onSelectSession: (key: string) => void
  selectedKey: string | null
}

const columnHelper = createColumnHelper<Session>()

export function SessionTable({ searchQuery, onSelectSession, selectedKey }: SessionTableProps) {
  const { data, isLoading } = useSessions()
  const [sorting, setSorting] = useState<SortingState>([])

  const sessions = data?.sessions || []

  const columns = useMemo(() => [
    columnHelper.accessor('key', {
      header: 'Session',
      cell: (info) => {
        const key = info.getValue()
        const channel = key.split(':')[0] || 'web'
        
        return (
          <div className="flex items-center gap-3">
            <div 
              className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
              style={{ backgroundColor: getChannelColor(channel) }}
            >
              {getChannelInitials(channel)}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-white truncate">{key}</p>
              <p className="text-xs text-gray-500 capitalize">{channel}</p>
            </div>
          </div>
        )
      },
    }),
    columnHelper.accessor('message_count', {
      header: 'Messages',
      cell: (info) => (
        <div className="flex items-center gap-2">
          <MessageSquare size={14} className="text-gray-500" />
          <span className="text-sm text-gray-300">{info.getValue()}</span>
        </div>
      ),
    }),
    columnHelper.accessor('last_updated', {
      header: 'Last Active',
      cell: (info) => {
        const value = info.getValue()
        return (
          <span className="text-sm text-gray-400">
            {value ? formatRelativeTime(value) : 'N/A'}
          </span>
        )
      },
    }),
    columnHelper.display({
      id: 'actions',
      header: '',
      cell: () => (
        <button className="p-1 rounded hover:bg-giga-hover text-gray-500 hover:text-white transition-colors">
          <MoreHorizontal size={16} />
        </button>
      ),
    }),
  ], [])

  const table = useReactTable({
    data: sessions,
    columns,
    state: {
      sorting,
      globalFilter: searchQuery,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: 10,
      },
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading sessions...</div>
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center">
        <MessageSquare size={48} className="text-gray-600 mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">No sessions yet</h3>
        <p className="text-sm text-gray-500 max-w-sm">
          Sessions will appear here when users start chatting with GigaBot
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-giga-darker z-10">
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th
                    key={header.id}
                    className={cn(
                      'px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-sidebar-border',
                      header.column.getCanSort() && 'cursor-pointer select-none hover:text-white'
                    )}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {header.column.getCanSort() && (
                        <span className="text-gray-600">
                          {{
                            asc: <ChevronUp size={14} />,
                            desc: <ChevronDown size={14} />,
                          }[header.column.getIsSorted() as string] ?? null}
                        </span>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map(row => (
              <tr
                key={row.id}
                onClick={() => onSelectSession(row.original.key)}
                className={cn(
                  'border-b border-sidebar-border cursor-pointer transition-colors',
                  'hover:bg-giga-hover',
                  selectedKey === row.original.key && 'bg-giga-hover'
                )}
              >
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-4 py-3">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-sidebar-border bg-giga-darker">
        <div className="text-sm text-gray-500">
          Showing {table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1} to{' '}
          {Math.min(
            (table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize,
            table.getFilteredRowModel().rows.length
          )}{' '}
          of {table.getFilteredRowModel().rows.length} sessions
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="p-2 rounded-lg bg-giga-card border border-sidebar-border text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={16} />
          </button>
          
          <span className="text-sm text-gray-400">
            Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
          </span>
          
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="p-2 rounded-lg bg-giga-card border border-sidebar-border text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
