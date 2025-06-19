import React, { useState, useEffect } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useAuth } from '../contexts/AuthContext';

// API URL configuration - same as App.tsx
const API_BASE_URL = (() => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  if (typeof window !== 'undefined' && (window as any).ENV?.REACT_APP_API_URL) {
    return (window as any).ENV.REACT_APP_API_URL;
  }
  if (import.meta.env.DEV) {
    return 'http://localhost:8000/api/v1';
  }
  return 'https://tq68ditf6b.execute-api.us-east-1.amazonaws.com/prod/api/v1';
})();

interface Task {
  id: string;
  title: string;
  description?: string;
  priority: number;
  is_completed: boolean;
  completed_at?: string;
  created_at: string;
  updated_at: string;
  source_session_id?: string;
}

interface TaskManagerProps {
  onClose?: () => void;
}

const TaskManagerSimple: React.FC<TaskManagerProps> = ({ onClose }) => {
  const { getAuthHeaders } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskDescription, setNewTaskDescription] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [showCompleted, setShowCompleted] = useState(false);

  // Set up drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Fetch tasks from API
  const fetchTasks = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/tasks?include_completed=${showCompleted}`, {
        headers: getAuthHeaders()
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch tasks: ${response.status}`);
      }
      
      const tasksData: Task[] = await response.json();
      setTasks(tasksData);
    } catch (err: any) {
      console.error('Error fetching tasks:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Load tasks on component mount and when showCompleted changes
  useEffect(() => {
    setLoading(true);
    fetchTasks();
  }, [showCompleted]);

  // Handle creating a new task
  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;

    try {
      const response = await fetch(`${API_BASE_URL}/tasks`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: newTaskTitle.trim(),
          description: newTaskDescription.trim() || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to create task: ${response.status}`);
      }

      const newTask: Task = await response.json();
      setTasks(prev => [...prev, newTask]);
      setNewTaskTitle('');
      setNewTaskDescription('');
      setShowAddForm(false);
    } catch (err: any) {
      console.error('Error creating task:', err);
      setError(err.message);
    }
  };

  // Handle completing a task
  const handleCompleteTask = async (taskId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/complete`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error(`Failed to complete task: ${response.status}`);
      }

      const updatedTask: Task = await response.json();
      setTasks(prev => prev.map(task => 
        task.id === taskId ? updatedTask : task
      ));
    } catch (err: any) {
      console.error('Error completing task:', err);
      setError(err.message);
    }
  };

  // Handle deleting a task
  const handleDeleteTask = async (taskId: string) => {
    if (!confirm('Are you sure you want to delete this task?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error(`Failed to delete task: ${response.status}`);
      }

      setTasks(prev => prev.filter(task => task.id !== taskId));
    } catch (err: any) {
      console.error('Error deleting task:', err);
      setError(err.message);
    }
  };

  // Handle drag and drop reordering
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;

    if (!over || active.id === over.id) return;

    const oldIndex = tasks.findIndex(task => task.id === active.id);
    const newIndex = tasks.findIndex(task => task.id === over.id);

    if (oldIndex === -1 || newIndex === -1) return;

    // Reorder tasks locally first for immediate UI feedback
    const reorderedTasks = arrayMove(tasks, oldIndex, newIndex);

    // Update priorities based on new order
    const taskOrders = reorderedTasks.map((task, index) => ({
      task_id: task.id,
      new_priority: index + 1
    }));

    setTasks(reorderedTasks);

    try {
      const response = await fetch(`${API_BASE_URL}/tasks/reorder`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ task_orders: taskOrders }),
      });

      if (!response.ok) {
        throw new Error(`Failed to reorder tasks: ${response.status}`);
      }

      // Refresh tasks to get updated priorities from server
      await fetchTasks();
    } catch (err: any) {
      console.error('Error reordering tasks:', err);
      setError(err.message);
      // Revert local changes on error
      await fetchTasks();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600">Loading tasks...</div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Task Manager</h1>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl"
          >
            ×
          </button>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          <span className="block sm:inline">{error}</span>
          <button 
            onClick={() => setError(null)} 
            className="float-right text-red-500 hover:text-red-700"
          >
            ×
          </button>
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-center mb-6">
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg font-medium"
        >
          {showAddForm ? 'Cancel' : '+ Add Task'}
        </button>
        
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={showCompleted}
            onChange={(e) => setShowCompleted(e.target.checked)}
            className="mr-2"
          />
          Show completed tasks
        </label>
        
        <div className="text-sm text-gray-600">
          {tasks.length} {tasks.length === 1 ? 'task' : 'tasks'}
          {showCompleted && ` (${tasks.filter(t => t.is_completed).length} completed)`}
        </div>
      </div>

      {/* Add Task Form */}
      {showAddForm && (
        <form onSubmit={handleCreateTask} className="bg-gray-50 p-4 rounded-lg mb-6">
          <div className="mb-4">
            <label htmlFor="taskTitle" className="block text-sm font-medium text-gray-700 mb-2">
              Task Title *
            </label>
            <input
              id="taskTitle"
              type="text"
              value={newTaskTitle}
              onChange={(e) => setNewTaskTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter task title..."
              required
            />
          </div>
          
          <div className="mb-4">
            <label htmlFor="taskDescription" className="block text-sm font-medium text-gray-700 mb-2">
              Description (optional)
            </label>
            <textarea
              id="taskDescription"
              value={newTaskDescription}
              onChange={(e) => setNewTaskDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter task description..."
              rows={3}
            />
          </div>
          
          <div className="flex gap-2">
            <button
              type="submit"
              className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded font-medium"
            >
              Create Task
            </button>
            <button
              type="button"
              onClick={() => setShowAddForm(false)}
              className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded font-medium"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Tasks List */}
      {tasks.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <div className="text-4xl mb-4">📝</div>
          <div className="text-lg">No tasks yet</div>
          <div className="text-sm">Create your first task to get started!</div>
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={tasks.map(task => task.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-3">
              {tasks.map((task) => (
                <SortableTaskItem
                  key={task.id}
                  task={task}
                  onComplete={handleCompleteTask}
                  onDelete={handleDeleteTask}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
      
      <div className="mt-8 text-sm text-gray-500 text-center">
        <p>✨ Drag tasks to reorder by priority!</p>
      </div>
    </div>
  );
};

// Sortable Task Item Component
interface SortableTaskItemProps {
  task: Task;
  onComplete: (taskId: string) => void;
  onDelete: (taskId: string) => void;
}

const SortableTaskItem: React.FC<SortableTaskItemProps> = ({ task, onComplete, onDelete }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ 
    id: task.id,
    disabled: task.is_completed // Disable drag for completed tasks
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`bg-white border rounded-lg p-4 shadow-sm ${
        isDragging ? 'shadow-lg z-10' : 'hover:shadow-md'
      } ${task.is_completed ? 'opacity-60' : ''}`}
    >
      <div className="flex items-start gap-3">
        {/* Drag Handle */}
        {!task.is_completed && (
          <div
            {...attributes}
            {...listeners}
            className="text-gray-400 hover:text-gray-600 cursor-grab active:cursor-grabbing mt-1 select-none"
            title="Drag to reorder"
          >
            ⋮⋮
          </div>
        )}
        
        {/* Task Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h3 className={`font-medium ${
                task.is_completed 
                  ? 'line-through text-gray-500' 
                  : 'text-gray-900'
              }`}>
                {task.title}
              </h3>
              
              {task.description && (
                <p className={`mt-1 text-sm ${
                  task.is_completed 
                    ? 'text-gray-400' 
                    : 'text-gray-600'
                }`}>
                  {task.description}
                </p>
              )}
              
              <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                <span>Priority: {task.priority}</span>
                <span>Created: {new Date(task.created_at).toLocaleDateString()}</span>
                {task.is_completed && task.completed_at && (
                  <span>Completed: {new Date(task.completed_at).toLocaleDateString()}</span>
                )}
                {task.source_session_id && (
                  <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded">
                    From Journal
                  </span>
                )}
              </div>
            </div>
            
            {/* Task Actions */}
            <div className="flex items-center gap-2 ml-4">
              {!task.is_completed && (
                <button
                  onClick={() => onComplete(task.id)}
                  className="text-green-600 hover:text-green-800 p-1"
                  title="Mark as completed"
                >
                  ✓
                </button>
              )}
              
              <button
                onClick={() => onDelete(task.id)}
                className="text-red-600 hover:text-red-800 p-1"
                title="Delete task"
              >
                🗑️
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TaskManagerSimple;