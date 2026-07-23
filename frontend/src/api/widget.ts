import { api } from './client'

export interface WidgetConfig {
  id: string
  widget_key: string
  is_enabled: boolean
  mode: 'floating' | 'inline'
  position: 'bottom-right' | 'bottom-left'
  button_color: string | null
  bg_color: string | null
  text_color: string | null
  greeting_title: string | null
  greeting_message: string | null
  success_message: string | null
  collect_phone: boolean
  created_at: string
  updated_at: string
}

export interface PublicWidgetConfig {
  mode: 'floating' | 'inline'
  position: 'bottom-right' | 'bottom-left'
  button_color: string
  bg_color: string
  text_color: string
  greeting_title: string
  greeting_message: string
  collect_phone: boolean
}

export const widgetApi = {
  getMyWidget: () => api.get<{ data: WidgetConfig }>('/widget/config'),
  updateMyWidget: (data: Partial<WidgetConfig>) => api.put<{ data: WidgetConfig }>('/widget/config', data),
  rotateKey: () => api.post<{ data: WidgetConfig }>('/widget/config/rotate-key'),
  getPublicConfig: (key: string) => api.get<{ data: PublicWidgetConfig }>(`/widget/public/${key}/config`),
  submit: (
    key: string,
    data: { name: string; email: string; phone?: string; message?: string; website?: string }
  ) => api.post<{ data: { message: string } }>(`/widget/public/${key}/submit`, data),
}
