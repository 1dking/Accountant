import { getInitials } from '@/lib/utils'

interface AwarenessUser {
  name: string
  color: string
}

interface CollaboratorAvatarsProps {
  users: AwarenessUser[]
}

export default function CollaboratorAvatars({ users }: CollaboratorAvatarsProps) {
  if (users.length === 0) return null

  const displayed = users.slice(0, 5)
  const overflow = users.length - displayed.length

  return (
    <div className="flex items-center -space-x-2">
      {displayed.map((user, i) => (
        <div
          key={i}
          className="h-7 w-7 rounded-full flex items-center justify-center text-[10px] font-medium text-white border-2 border-white"
          style={{ backgroundColor: user.color }}
          title={user.name}
        >
          {getInitials(user.name)}
        </div>
      ))}
      {overflow > 0 && (
        <div className="h-7 w-7 rounded-full flex items-center justify-center text-[10px] font-medium text-gray-600 dark:text-gray-400 bg-gray-200 dark:bg-gray-700 border-2 border-white">
          +{overflow}
        </div>
      )}
    </div>
  )
}
