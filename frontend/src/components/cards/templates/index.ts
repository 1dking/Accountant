import ClassicCard from './ClassicCard'
import ModernCard from './ModernCard'
import MinimalCard from './MinimalCard'
import GradientCard from './GradientCard'
import SplitCard from './SplitCard'
import BoldCard from './BoldCard'

/** Single registry both the editor and the public page render from —
 * must stay in sync with backend/app/cards/schemas.py::TEMPLATES. */
export const CARD_TEMPLATES = {
  classic: ClassicCard,
  modern: ModernCard,
  minimal: MinimalCard,
  gradient: GradientCard,
  split: SplitCard,
  bold: BoldCard,
} as const

export type CardTemplateId = keyof typeof CARD_TEMPLATES

export const CARD_TEMPLATE_OPTIONS: { id: CardTemplateId; label: string }[] = [
  { id: 'classic', label: 'Classic' },
  { id: 'modern', label: 'Modern' },
  { id: 'minimal', label: 'Minimal' },
  { id: 'gradient', label: 'Gradient' },
  { id: 'split', label: 'Split' },
  { id: 'bold', label: 'Bold' },
]
