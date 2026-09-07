import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';
import {
  Plus,
  Search,
  FileText,
  Send,
  Eye,
  PenLine,
  CheckCircle,
  XCircle,
  DollarSign,
  LayoutList,
  Kanban,
  MoreHorizontal,
  X,
  Loader2,
} from 'lucide-react';
import {
  listProposals,
  getProposalStats,
  createProposal,
  deleteProposal,
  sendProposal,
  cloneProposal,
  declineProposal,
  completeProposal,
  convertToTemplate,
  refundProposal,
} from '@/api/proposals';
import type { ProposalListItem, ProposalStatus, ProposalStats } from '@/api/proposals';
import { listContacts } from '@/api/contacts';
import { cn, formatDate, uiLocale } from '@/lib/utils';
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat(uiLocale(), { style: 'currency', currency }).format(amount);

const STATUS_CONFIG: Record<
  ProposalStatus,
  { label: string; color: string; bgColor: string; icon: typeof FileText }
> = {
  draft: {
    label: i18n.t('ui:ProposalsPage.draft'),
    color: 'text-gray-700 dark:text-gray-300',
    bgColor: 'bg-gray-100 dark:bg-gray-800',
    icon: FileText,
  },
  sent: {
    label: i18n.t('ui:ProposalsPage.sent'),
    color: 'text-blue-700 dark:text-blue-300',
    bgColor: 'bg-blue-100 dark:bg-blue-900/40',
    icon: Send,
  },
  viewed: {
    label: i18n.t('ui:ProposalsPage.viewed'),
    color: 'text-yellow-700 dark:text-yellow-300',
    bgColor: 'bg-yellow-100 dark:bg-yellow-900/40',
    icon: Eye,
  },
  waiting_signature: {
    label: i18n.t('ui:ProposalsPage.waitingSignature'),
    color: 'text-orange-700 dark:text-orange-300',
    bgColor: 'bg-orange-100 dark:bg-orange-900/40',
    icon: PenLine,
  },
  signed: {
    label: i18n.t('ui:ProposalsPage.signed'),
    color: 'text-green-700 dark:text-green-300',
    bgColor: 'bg-green-100 dark:bg-green-900/40',
    icon: CheckCircle,
  },
  declined: {
    label: i18n.t('ui:ProposalsPage.declined'),
    color: 'text-red-700 dark:text-red-300',
    bgColor: 'bg-red-100 dark:bg-red-900/40',
    icon: XCircle,
  },
  paid: {
    label: i18n.t('ui:ProposalsPage.paid'),
    color: 'text-emerald-700 dark:text-emerald-300',
    bgColor: 'bg-emerald-100 dark:bg-emerald-900/40',
    icon: DollarSign,
  },
};

const KANBAN_COLUMNS: ProposalStatus[] = [
  'draft',
  'sent',
  'viewed',
  'waiting_signature',
  'signed',
  'paid',
];

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: i18n.t('ui:ProposalsPage.allStatuses') },
  { value: 'draft', label: i18n.t('ui:ProposalsPage.draft') },
  { value: 'sent', label: i18n.t('ui:ProposalsPage.sent') },
  { value: 'viewed', label: i18n.t('ui:ProposalsPage.viewed') },
  { value: 'waiting_signature', label: i18n.t('ui:ProposalsPage.waitingSignature') },
  { value: 'signed', label: i18n.t('ui:ProposalsPage.signed') },
  { value: 'declined', label: i18n.t('ui:ProposalsPage.declined') },
  { value: 'paid', label: i18n.t('ui:ProposalsPage.paid') },
];

// ---------------------------------------------------------------------------
// StatusBadge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: ProposalStatus }) {
  const config = STATUS_CONFIG[status];
  if (!config) return <span className="text-xs text-gray-500">{status}</span>;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium',
        config.bgColor,
        config.color,
      )}
    >
      {config.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// ActionsDropdown
// ---------------------------------------------------------------------------

function ActionsDropdown({
  proposal,
  onAction,
}: {
  proposal: ProposalListItem;
  onAction: (action: string, proposal: ProposalListItem) => void;
}) {
  const { t } = useTranslation('ui')
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [open]);

  const items: { label: string; action: string; show: boolean; danger?: boolean }[] = [
    { label: t('ui:ProposalsPage.view'), action: 'view', show: true },
    { label: t('ui:ProposalsPage.edit'), action: 'edit', show: proposal.status === 'draft' },
    { label: t('ui:ProposalsPage.send'), action: 'send', show: proposal.status === 'draft' },
    { label: t('ui:ProposalsPage.clone'), action: 'clone', show: true },
    { label: t('ui:ProposalsPage.downloadPdf'), action: 'download', show: true },
    { label: t('ui:ProposalsPage.shareLink'), action: 'share', show: !!proposal.public_token },
    { label: t('ui:ProposalsPage.markComplete'), action: 'complete', show: proposal.status === 'signed' },
    {
      label: t('ui:ProposalsPage.decline'),
      action: 'decline',
      show: ['sent', 'viewed', 'waiting_signature'].includes(proposal.status),
    },
    {
      label: t('ui:ProposalsPage.refund'),
      action: 'refund',
      show:
        proposal.status === 'paid' &&
        (proposal.refunded_amount ?? 0) < proposal.value,
    },
    { label: t('ui:ProposalsPage.convertToTemplate'), action: 'convert_template', show: true },
    { label: t('ui:ProposalsPage.delete'), action: 'delete', show: true, danger: true },
  ];

  const visible = items.filter((i) => i.show);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      >
        <MoreHorizontal className="w-4 h-4 text-gray-500" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50 py-1">
          {visible.map((item) => (
            <button
              key={item.action}
              onClick={(e) => {
                e.stopPropagation();
                setOpen(false);
                onAction(item.action, proposal);
              }}
              className={cn(
                'w-full text-left px-3 py-2 text-sm transition-colors',
                item.danger
                  ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800',
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RefundModal
// ---------------------------------------------------------------------------

function RefundModal({
  proposal,
  onClose,
}: {
  proposal: ProposalListItem;
  onClose: () => void;
}) {
  const { t } = useTranslation('ui')
  const queryClient = useQueryClient();
  const alreadyRefunded = proposal.refunded_amount ?? 0;
  const remaining = Math.max(0, proposal.value - alreadyRefunded);

  const [mode, setMode] = useState<'full' | 'partial'>('full');
  const [amount, setAmount] = useState<string>(remaining.toFixed(2));

  const refundMutation = useMutation({
    mutationFn: () => refundProposal(proposal.id, mode === 'partial' ? Number(amount) : undefined),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success(
        res.data.fully_refunded
          ? `Fully refunded ${formatCurrency(res.data.total_refunded, proposal.currency)}`
          : `Refunded ${formatCurrency(res.data.amount, proposal.currency)}`,
      );
      onClose();
    },
    onError: (err: unknown) =>
      toast.error(err instanceof Error ? err.message : 'Refund failed'),
  });

  const partialValue = Number(amount);
  const partialInvalid =
    mode === 'partial' && (!Number.isFinite(partialValue) || partialValue <= 0 || partialValue > remaining + 1e-9);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">{t('ui:ProposalsPage.refundPayment')}</h2>
          <button onClick={onClose} className="p-1 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            <p className="font-medium text-gray-900 dark:text-gray-100">{proposal.title}</p>
            <p className="mt-0.5">
             {t('ui:ProposalsPage.paid')} {formatCurrency(proposal.value, proposal.currency)}
              {alreadyRefunded > 0 && (
                <> {t('ui:ProposalsPage.alreadyRefunded')} {formatCurrency(alreadyRefunded, proposal.currency)}</>
              )}
            </p>
            <p className="mt-0.5 text-gray-500">
             {t('ui:ProposalsPage.refundableBalance')} {formatCurrency(remaining, proposal.currency)}
            </p>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => setMode('full')}
              className={cn(
                'flex-1 px-3 py-2 text-sm rounded-lg border transition-colors',
                mode === 'full'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400 font-medium'
                  : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400',
              )}
            >
             {t('ui:ProposalsPage.full')}{formatCurrency(remaining, proposal.currency)})
            </button>
            <button
              onClick={() => setMode('partial')}
              className={cn(
                'flex-1 px-3 py-2 text-sm rounded-lg border transition-colors',
                mode === 'partial'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400 font-medium'
                  : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400',
              )}
            >
             {t('ui:ProposalsPage.customAmount')}
            </button>
          </div>

          {mode === 'partial' && (
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
               {t('ui:ProposalsPage.amountToRefund')}{proposal.currency})
              </label>
              <input
                type="number"
                min="0.01"
                max={remaining}
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
              {partialInvalid && (
                <p className="text-[11px] text-red-500 mt-1">
                 {t('ui:ProposalsPage.enterAnAmountBetween0')} {formatCurrency(remaining, proposal.currency)}.
                </p>
              )}
            </div>
          )}

          <p className="text-[11px] text-gray-400 dark:text-gray-500">
           {t('ui:ProposalsPage.theRefundIsIssuedTo')}
          </p>
        </div>

        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700"
          >
           {t('ui:ProposalsPage.cancel')}
          </button>
          <button
            onClick={() => refundMutation.mutate()}
            disabled={refundMutation.isPending || partialInvalid || remaining <= 0}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
          >
            {refundMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
           {t('ui:ProposalsPage.refund')}{' '}
            {formatCurrency(mode === 'full' ? remaining : partialValue || 0, proposal.currency)}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CreateProposalModal
// ---------------------------------------------------------------------------

function CreateProposalModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation('ui')
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState('');
  const [contactId, setContactId] = useState('');

  const contactsQuery = useQuery({
    queryKey: ['contacts', { forProposalCreate: true }],
    queryFn: () => listContacts({ page_size: 100 }),
  });

  const contacts = contactsQuery.data?.data ?? [];

  const createMutation = useMutation({
    mutationFn: (data: { contact_id: string; title: string }) => createProposal(data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success(t('ui:ProposalsPage.proposalCreated'));
      navigate(`/proposals/${result.data.id}/edit`);
    },
    onError: () => {
      toast.error(t('ui:ProposalsPage.failedToCreateProposal'));
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !contactId) return;
    createMutation.mutate({ contact_id: contactId, title: title.trim() });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('ui:ProposalsPage.newProposal')}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="proposal-title"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
             {t('ui:ProposalsPage.title')}
            </label>
            <input
              id="proposal-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t('ui:ProposalsPage.eGWebsiteRedesignProposal')}
              required
              autoFocus
              className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label
              htmlFor="proposal-contact"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
             {t('ui:ProposalsPage.contact')}
            </label>
            <select
              id="proposal-contact"
              value={contactId}
              onChange={(e) => setContactId(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">{t('ui:ProposalsPage.selectAContact')}</option>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.company_name}
                  {c.contact_name ? ` (${c.contact_name})` : ''}
                </option>
              ))}
            </select>
            {contactsQuery.isLoading && (
              <p className="text-xs text-gray-400 mt-1">{t('ui:ProposalsPage.loadingContacts')}</p>
            )}
          </div>
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
            >
             {t('ui:ProposalsPage.cancel')}
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || !title.trim() || !contactId}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {createMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
             {t('ui:ProposalsPage.create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// KanbanView
// ---------------------------------------------------------------------------

function KanbanView({
  proposals,
  onAction,
}: {
  proposals: ProposalListItem[];
  onAction: (action: string, proposal: ProposalListItem) => void;
}) {
  const { t } = useTranslation('ui')
  const navigate = useNavigate();

  const grouped = KANBAN_COLUMNS.reduce(
    (acc, status) => {
      acc[status] = proposals.filter((p) => p.status === status);
      return acc;
    },
    {} as Record<ProposalStatus, ProposalListItem[]>,
  );

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {KANBAN_COLUMNS.map((status) => {
        const config = STATUS_CONFIG[status];
        const items = grouped[status] ?? [];
        return (
          <div key={status} className="flex-shrink-0 w-72">
            {/* Column header */}
            <div
              className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-t-lg border border-b-0 border-gray-200 dark:border-gray-700',
                config.bgColor,
              )}
            >
              <config.icon className={cn('w-4 h-4', config.color)} />
              <span className={cn('text-sm font-medium', config.color)}>{config.label}</span>
              <span
                className={cn(
                  'ml-auto text-xs font-medium rounded-full px-2 py-0.5',
                  config.bgColor,
                  config.color,
                )}
              >
                {items.length}
              </span>
            </div>
            {/* Cards */}
            <div className="bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-b-lg p-2 min-h-[200px] space-y-2">
              {items.length === 0 && (
                <p className="text-xs text-gray-400 dark:text-gray-500 text-center py-6">
                 {t('ui:ProposalsPage.noProposals')}
                </p>
              )}
              {items.map((proposal) => (
                <div
                  key={proposal.id}
                  onClick={() => navigate(`/proposals/${proposal.id}`)}
                  className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 cursor-pointer hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {proposal.title}
                    </h4>
                    <ActionsDropdown proposal={proposal} onAction={onAction} />
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
                    {proposal.contact?.company_name ?? t('ui:ProposalsPage.noContact')}
                  </p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {formatCurrency(proposal.value, proposal.currency)}
                    </span>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {formatDate(proposal.created_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main: ProposalsPage
// ---------------------------------------------------------------------------

export default function ProposalsPage() {
  const { t } = useTranslation('ui')
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // UI state
  const [view, setView] = useState<'list' | 'kanban'>('list');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [refundTarget, setRefundTarget] = useState<ProposalListItem | null>(null);

  // Data queries
  const statsQuery = useQuery({
    queryKey: ['proposal-stats'],
    queryFn: getProposalStats,
  });

  const proposalsQuery = useQuery({
    queryKey: ['proposals', { search, status: statusFilter, date_from: dateFrom, date_to: dateTo, page }],
    queryFn: () =>
      listProposals({
        search: search || undefined,
        status: statusFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page: String(page),
        page_size: '20',
      }),
  });

  const proposals = proposalsQuery.data?.data ?? [];
  const meta = proposalsQuery.data?.meta;
  const stats: ProposalStats | null = statsQuery.data?.data ?? null;

  // Mutations
  const deleteMutation = useMutation({
    mutationFn: deleteProposal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success(t('ui:ProposalsPage.proposalDeleted'));
    },
    onError: () => toast.error(t('ui:ProposalsPage.failedToDeleteProposal')),
  });

  const sendMutation = useMutation({
    mutationFn: sendProposal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success(t('ui:ProposalsPage.proposalSent'));
    },
    onError: () => toast.error(t('ui:ProposalsPage.failedToSendProposal')),
  });

  const cloneMutation = useMutation({
    mutationFn: cloneProposal,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success(t('ui:ProposalsPage.proposalCloned'));
      navigate(`/proposals/${result.data.id}`);
    },
    onError: () => toast.error(t('ui:ProposalsPage.failedToCloneProposal')),
  });

  const declineMutation = useMutation({
    mutationFn: declineProposal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success(t('ui:ProposalsPage.proposalDeclined'));
    },
    onError: () => toast.error(t('ui:ProposalsPage.failedToDeclineProposal')),
  });

  const completeMutation = useMutation({
    mutationFn: completeProposal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success(t('ui:ProposalsPage.proposalMarkedAsComplete'));
    },
    onError: () => toast.error(t('ui:ProposalsPage.failedToCompleteProposal')),
  });

  const convertMutation = useMutation({
    mutationFn: convertToTemplate,
    onSuccess: () => {
      toast.success(t('ui:ProposalsPage.convertedToTemplate'));
    },
    onError: () => toast.error(t('ui:ProposalsPage.failedToConvertToTemplate')),
  });

  // Action handler
  const handleAction = useCallback(
    (action: string, proposal: ProposalListItem) => {
      switch (action) {
        case 'view':
          navigate(`/proposals/${proposal.id}`);
          break;
        case 'edit':
          navigate(`/proposals/${proposal.id}/edit`);
          break;
        case 'send':
          sendMutation.mutate(proposal.id);
          break;
        case 'clone':
          cloneMutation.mutate(proposal.id);
          break;
        case 'download':
          // Download is handled via direct navigation to download endpoint
          window.open(`/api/proposals/${proposal.id}/pdf`, '_blank');
          break;
        case 'share':
          if (proposal.public_token) {
            const url = `${window.location.origin}/proposals/sign/${proposal.public_token}`;
            navigator.clipboard.writeText(url).then(() => {
              toast.success(t('ui:ProposalsPage.linkCopiedToClipboard'));
            });
          }
          break;
        case 'complete':
          completeMutation.mutate(proposal.id);
          break;
        case 'decline':
          declineMutation.mutate(proposal.id);
          break;
        case 'convert_template':
          convertMutation.mutate(proposal.id);
          break;
        case 'refund':
          setRefundTarget(proposal);
          break;
        case 'delete':
          if (window.confirm(t('ui:ProposalsPage.areYouSureYouWant'))) {
            deleteMutation.mutate(proposal.id);
          }
          break;
      }
    },
    [navigate, sendMutation, cloneMutation, completeMutation, declineMutation, convertMutation, deleteMutation],
  );

  // Stat cards
  const statCards = [
    {
      label: t('ui:ProposalsPage.total'),
      value: stats ? stats.total_proposals.toLocaleString() : '--',
      icon: FileText,
      iconColor: 'text-purple-600 dark:text-purple-400',
      iconBg: 'bg-purple-50 dark:bg-purple-900/30',
    },
    {
      label: t('ui:ProposalsPage.draft'),
      value: stats ? stats.draft_count.toLocaleString() : '--',
      icon: FileText,
      iconColor: 'text-gray-600 dark:text-gray-400',
      iconBg: 'bg-gray-100 dark:bg-gray-800',
    },
    {
      label: t('ui:ProposalsPage.sent'),
      value: stats ? stats.sent_count.toLocaleString() : '--',
      icon: Send,
      iconColor: 'text-blue-600 dark:text-blue-400',
      iconBg: 'bg-blue-50 dark:bg-blue-900/30',
    },
    {
      label: t('ui:ProposalsPage.viewed'),
      value: stats ? stats.viewed_count.toLocaleString() : '--',
      icon: Eye,
      iconColor: 'text-yellow-600 dark:text-yellow-400',
      iconBg: 'bg-yellow-50 dark:bg-yellow-900/30',
    },
    {
      label: t('ui:ProposalsPage.signed'),
      value: stats ? stats.signed_count.toLocaleString() : '--',
      icon: CheckCircle,
      iconColor: 'text-green-600 dark:text-green-400',
      iconBg: 'bg-green-50 dark:bg-green-900/30',
    },
    {
      label: t('ui:ProposalsPage.paid'),
      value: stats ? stats.paid_count.toLocaleString() : '--',
      icon: DollarSign,
      iconColor: 'text-emerald-600 dark:text-emerald-400',
      iconBg: 'bg-emerald-50 dark:bg-emerald-900/30',
    },
    {
      label: t('ui:ProposalsPage.totalValue'),
      value: stats ? formatCurrency(stats.total_value) : '--',
      icon: DollarSign,
      iconColor: 'text-indigo-600 dark:text-indigo-400',
      iconBg: 'bg-indigo-50 dark:bg-indigo-900/30',
    },
    {
      label: t('ui:ProposalsPage.signedValue'),
      value: stats ? formatCurrency(stats.signed_value) : '--',
      icon: CheckCircle,
      iconColor: 'text-green-600 dark:text-green-400',
      iconBg: 'bg-green-50 dark:bg-green-900/30',
    },
  ];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{t('ui:ProposalsPage.proposals')}</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
         {t('ui:ProposalsPage.newProposal')}
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 mb-6">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <div className={cn('p-1.5 rounded-lg', card.iconBg)}>
                <card.icon className={cn('w-3.5 h-3.5', card.iconColor)} />
              </div>
            </div>
            <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">{card.value}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">{card.label}</p>
          </div>
        ))}
      </div>

      {/* Filters row */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500" />
          <input
            type="text"
            placeholder={t('ui:ProposalsPage.searchProposals')}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-10 pr-4 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
          />
        </div>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Date from */}
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => {
            setDateFrom(e.target.value);
            setPage(1);
          }}
          placeholder={t('ui:ProposalsPage.from')}
          className="px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
        />

        {/* Date to */}
        <input
          type="date"
          value={dateTo}
          onChange={(e) => {
            setDateTo(e.target.value);
            setPage(1);
          }}
          placeholder={t('ui:ProposalsPage.to')}
          className="px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
        />

        {/* View toggle */}
        <div className="flex items-center border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden ml-auto">
          <button
            onClick={() => setView('list')}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 text-sm transition-colors',
              view === 'list'
                ? 'bg-blue-600 text-white'
                : 'bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800',
            )}
          >
            <LayoutList className="w-4 h-4" />
           {t('ui:ProposalsPage.list')}
          </button>
          <button
            onClick={() => setView('kanban')}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 text-sm transition-colors',
              view === 'kanban'
                ? 'bg-blue-600 text-white'
                : 'bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800',
            )}
          >
            <Kanban className="w-4 h-4" />
           {t('ui:ProposalsPage.kanban')}
          </button>
        </div>
      </div>

      {/* Loading */}
      {proposalsQuery.isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-500 dark:text-gray-400">{t('ui:ProposalsPage.loadingProposals')}</span>
        </div>
      )}

      {/* Empty state */}
      {!proposalsQuery.isLoading && proposals.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="p-4 rounded-full bg-gray-100 dark:bg-gray-800 mb-4">
            <FileText className="w-8 h-8 text-gray-400 dark:text-gray-500" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">
           {t('ui:ProposalsPage.noProposalsYet')}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4 max-w-sm">
           {t('ui:ProposalsPage.createYourFirstProposalTo')}
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm"
          >
            <Plus className="w-4 h-4" />
           {t('ui:ProposalsPage.newProposal')}
          </button>
        </div>
      )}

      {/* List view */}
      {!proposalsQuery.isLoading && proposals.length > 0 && view === 'list' && (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700">
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                 {t('ui:ProposalsPage.title')}
                </th>
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                 {t('ui:ProposalsPage.contact')}
                </th>
                <th className="text-right px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                 {t('ui:ProposalsPage.value')}
                </th>
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                 {t('ui:ProposalsPage.status')}
                </th>
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                 {t('ui:ProposalsPage.created')}
                </th>
                <th className="text-right px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                 {t('ui:ProposalsPage.actions')}
                </th>
              </tr>
            </thead>
            <tbody>
              {proposals.map((proposal) => (
                <tr
                  key={proposal.id}
                  onClick={() => navigate(`/proposals/${proposal.id}`)}
                  className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                >
                  <td className="px-5 py-3">
                    <div>
                      <p className="font-medium text-gray-900 dark:text-gray-100">
                        {proposal.title}
                      </p>
                      <p className="text-xs text-gray-400 dark:text-gray-500">
                        {proposal.proposal_number}
                      </p>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-gray-700 dark:text-gray-300">
                    {proposal.contact?.company_name ?? '--'}
                  </td>
                  <td className="px-5 py-3 text-right font-medium text-gray-900 dark:text-gray-100">
                    {formatCurrency(proposal.value, proposal.currency)}
                  </td>
                  <td className="px-5 py-3">
                    <StatusBadge status={proposal.status} />
                  </td>
                  <td className="px-5 py-3 text-gray-500 dark:text-gray-400">
                    {formatDate(proposal.created_at)}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <ActionsDropdown proposal={proposal} onAction={handleAction} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Kanban view */}
      {!proposalsQuery.isLoading && proposals.length > 0 && view === 'kanban' && (
        <KanbanView proposals={proposals} onAction={handleAction} />
      )}

      {/* Pagination (list view only) */}
      {view === 'list' && meta && meta.total_pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">
           {t('ui:ProposalsPage.page')} {meta.page} of {meta.total_pages} ({meta.total_count} {t('ui:ProposalsPage.total_2')}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
             {t('ui:ProposalsPage.previous')}
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= meta.total_pages}
              className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
             {t('ui:ProposalsPage.next')}
            </button>
          </div>
        </div>
      )}

      {/* Create modal */}
      {showCreateModal && <CreateProposalModal onClose={() => setShowCreateModal(false)} />}
      {refundTarget && (
        <RefundModal proposal={refundTarget} onClose={() => setRefundTarget(null)} />
      )}
    </div>
  );
}
