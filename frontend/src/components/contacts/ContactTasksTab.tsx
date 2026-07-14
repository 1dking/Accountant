import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CheckSquare, Loader2, Plus, Trash2 } from 'lucide-react'
import {
  createTask,
  deleteTask,
  listTasks,
  updateTask,
  type Task,
  type TaskPriority,
} from '@/api/tasks'
import { EmptyState, LoadingSkeleton, formatDate } from './contactDetailUtils'

const PRIORITY_STYLES: Record<TaskPriority, string> = {
  high: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  medium: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  low: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
}

function isOverdue(task: Task): boolean {
  if (!task.due_date || task.status === 'done' || task.status === 'cancelled') return false
  return new Date(task.due_date) < new Date(new Date().toDateString())
}

export default function ContactTasksTab({ contactId }: { contactId: string }) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<TaskPriority>('medium')
  const [dueDate, setDueDate] = useState('')

  const queryKey = ['contact-tasks', contactId]

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => listTasks({ contact_id: contactId }),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey })

  const createMutation = useMutation({
    mutationFn: () =>
      createTask({
        title: title.trim(),
        contact_id: contactId,
        priority,
        due_date: dueDate || null,
      }),
    onSuccess: () => {
      setTitle('')
      setPriority('medium')
      setDueDate('')
      invalidate()
    },
    onError: (err) =>
      toast.error(
        `Couldn't create the task: ${err instanceof Error ? err.message : 'Unknown error'}`,
      ),
  })

  const toggleMutation = useMutation({
    mutationFn: (task: Task) =>
      updateTask(task.id, { status: task.status === 'done' ? 'todo' : 'done' }),
    onSuccess: invalidate,
    onError: (err) =>
      toast.error(
        `Couldn't update the task: ${err instanceof Error ? err.message : 'Unknown error'}`,
      ),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTask(id),
    onSuccess: invalidate,
    onError: (err) =>
      toast.error(
        `Couldn't delete the task: ${err instanceof Error ? err.message : 'Unknown error'}`,
      ),
  })

  const tasks = data?.data ?? []
  const open = tasks.filter((t) => t.status !== 'done' && t.status !== 'cancelled')
  const closed = tasks.filter((t) => t.status === 'done' || t.status === 'cancelled')

  const canSubmit = title.trim().length > 0 && !createMutation.isPending

  const renderRow = (task: Task) => {
    const done = task.status === 'done'
    return (
      <li
        key={task.id}
        className="group flex items-center gap-3 px-3 py-2 border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
      >
        <input
          type="checkbox"
          checked={done}
          onChange={() => toggleMutation.mutate(task)}
          aria-label={done ? `Reopen ${task.title}` : `Complete ${task.title}`}
          className="shrink-0"
        />
        <div className="min-w-0 flex-1">
          <p
            className={`text-sm truncate ${
              done
                ? 'line-through text-gray-400 dark:text-gray-600'
                : 'text-gray-900 dark:text-gray-100'
            }`}
          >
            {task.title}
          </p>
          {task.due_date && (
            <p
              className={`text-xs ${
                isOverdue(task)
                  ? 'text-red-600 dark:text-red-400 font-medium'
                  : 'text-gray-500 dark:text-gray-500'
              }`}
            >
              Due {formatDate(task.due_date)}
              {isOverdue(task) && ' · overdue'}
            </p>
          )}
        </div>
        <span
          className={`shrink-0 px-2 py-0.5 rounded text-xs font-medium ${PRIORITY_STYLES[task.priority]}`}
        >
          {task.priority}
        </span>
        <button
          onClick={() => deleteMutation.mutate(task.id)}
          aria-label={`Delete ${task.title}`}
          className="shrink-0 p-1 text-gray-400 opacity-0 group-hover:opacity-100 hover:text-red-600 rounded transition-opacity"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </li>
    )
  }

  if (isLoading) return <LoadingSkeleton />

  return (
    <div className="space-y-4">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (canSubmit) createMutation.mutate()
        }}
        className="flex flex-wrap items-center gap-2"
      >
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Add a task..."
          className="flex-1 min-w-[12rem] px-3 py-1.5 text-sm border rounded-lg bg-white dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
        />
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value as TaskPriority)}
          aria-label="Priority"
          className="px-2 py-1.5 text-sm border rounded-lg bg-white dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
        >
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
        <input
          type="date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
          aria-label="Due date"
          className="px-2 py-1.5 text-sm border rounded-lg bg-white dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
        />
        <button
          type="submit"
          disabled={!canSubmit}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {createMutation.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Plus className="h-3.5 w-3.5" />
          )}
          Add
        </button>
      </form>

      {tasks.length === 0 ? (
        <EmptyState
          icon={CheckSquare}
          title="No tasks"
          description="Add a task to track follow-up work for this contact."
        />
      ) : (
        <div className="space-y-4">
          {open.length > 0 && (
            <ul className="border-t border-gray-100 dark:border-gray-700">
              {open.map(renderRow)}
            </ul>
          )}
          {closed.length > 0 && (
            <div>
              <p className="px-3 py-1 text-xs font-medium text-gray-500 dark:text-gray-500 uppercase tracking-wide">
                Completed ({closed.length})
              </p>
              <ul className="border-t border-gray-100 dark:border-gray-700">
                {closed.map(renderRow)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
