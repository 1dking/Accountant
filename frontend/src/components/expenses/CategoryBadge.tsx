import type { ExpenseCategory } from '@/types/models'

interface CategoryBadgeProps {
  category: ExpenseCategory | null
}

export default function CategoryBadge({ category }: CategoryBadgeProps) {
  if (!category) {
    return (
      <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">
        Uncategorized
      </span>
    )
  }

  return (
    <span
      className="inline-block px-2 py-0.5 text-xs rounded-full font-medium"
      style={{
        backgroundColor: category.color ? category.color + '18' : '#f3f4f6',
        color: category.color || '#6b7280',
      }}
    >
      {category.name}
    </span>
  )
}
