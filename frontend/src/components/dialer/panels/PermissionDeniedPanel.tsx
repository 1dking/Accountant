import { AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export default function PermissionDeniedPanel() {
  const { t } = useTranslation('ui')
  return (
    <div className="px-6 py-8 space-y-3 text-center">
      <AlertCircle className="h-8 w-8 mx-auto text-red-400" />
      <div>
        <div className="text-sm font-medium text-[color:var(--lg-text-primary)] mb-1">
         {t('ui:PermissionDeniedPanel.microphoneAccessDenied')}
        </div>
        <div className="text-xs text-[color:var(--lg-text-secondary)]">
         {t('ui:PermissionDeniedPanel.reEnableMicrophonePermissionIn')}
        </div>
      </div>
    </div>
  )
}
