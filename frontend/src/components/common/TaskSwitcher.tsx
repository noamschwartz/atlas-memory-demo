/**
 * TaskSwitcher — Horizontal pill bar for switching between tasks/modes.
 *
 * A compact row of clickable pills with icons, used for top-level mode
 * switching (e.g., "Dashboard", "Explorer", "Settings").
 *
 * Usage:
 *   <TaskSwitcher
 *     tasks={[
 *       { id: 'planner', label: 'Planner', icon: 'calendar', color: '#003D29' },
 *       { id: 'advisor', label: 'Advisor', icon: 'brush', color: '#5A2D82' },
 *     ]}
 *     activeTaskId="planner"
 *     onSwitch={(task) => setActiveTask(task)}
 *   />
 */

import { EuiIcon } from '@elastic/eui'

export interface TaskDef {
  id: string
  label: string
  icon: string
  /** Accent colour for the active state (border + tint) */
  color: string
}

export interface TaskSwitcherProps<T extends TaskDef = TaskDef> {
  tasks: T[]
  activeTaskId: string
  onSwitch: (task: T) => void
}

export function TaskSwitcher<T extends TaskDef>({
  tasks,
  activeTaskId,
  onSwitch,
}: TaskSwitcherProps<T>) {
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {tasks.map((task) => {
        const isActive = task.id === activeTaskId
        return (
          <button
            key={task.id}
            onClick={() => onSwitch(task)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 14px',
              borderRadius: 20,
              border: isActive
                ? `2px solid ${task.color}`
                : '2px solid var(--euiColorLightShade)',
              background: isActive
                ? `${task.color}18`
                : 'var(--euiColorEmptyShade)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              fontWeight: isActive ? 600 : 400,
              fontSize: 13,
              color: isActive ? task.color : 'var(--euiTextColor)',
              whiteSpace: 'nowrap',
            }}
          >
            <EuiIcon type={task.icon} size="s" color={isActive ? task.color : 'subdued'} />
            {task.label}
          </button>
        )
      })}
    </div>
  )
}

export default TaskSwitcher
