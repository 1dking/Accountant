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
} from '@/api/proposals';
import type { ProposalListItem, ProposalStatus, ProposalStats } from '@/api/proposals';
import { listContacts } from '@/api/contacts';
import { cn, formatDate } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);

const STATUS_CONFIG: Record<
  ProposalStatus,
  { label: string; color: string; bgColor: string; icon: typeof FileText }
> = {
  draft: {
    label: 'Draft',
    color: 'text-gray-700 dark:text-gray-300',
    bgColor: 'bg-gray-100 dark:bg-gray-800',
    icon: FileText,
  },
  sent: {
    label: 'Sent',
    color: 'text-blue-700 dark:text-blue-300',
    bgColor: 'bg-blue-100 dark:bg-blue-900/40',
    icon: Send,
  },
  viewed: {
    label: 'Viewed',
    color: 'text-yellow-700 dark:text-yellow-300',
    bgColor: 'bg-yellow-100 dark:bg-yellow-900/40',
    icon: Eye,
  },
  waiting_signature: {
    label: 'Waiting Signature',
    color: 'text-orange-700 dark:text-orange-300',
    bgColor: 'bg-orange-100 dark:bg-orange-900/40',
    icon: PenLine,
  },
  signed: {
    label: 'Signed',
    color: 'text-green-700 dark:text-green-300',
    bgColor: 'bg-green-100 dark:bg-green-900/40',
    icon: CheckCircle,
  },
  declined: {
    label: 'Declined',
    color: 'text-red-700 dark:text-red-300',
    bgColor: 'bg-red-100 dark:bg-red-900/40',
    icon: XCircle,
  },
  paid: {
    label: 'Paid',
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
  { value: '', label: 'All Statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'sent', label: 'Sent' },
  { value: 'viewed', label: 'Viewed' },
  { value: 'waiting_signature', label: 'Waiting Signature' },
  { value: 'signed', label: 'Signed' },
  { value: 'declined', label: 'Declined' },
  { value: 'paid', label: 'Paid' },
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
    { label: 'View', action: 'view', show: true },
    { label: 'Edit', action: 'edit', show: proposal.status === 'draft' },
    { label: 'Send', action: 'send', show: proposal.status === 'draft' },
    { label: 'Clone', action: 'clone', show: true },
    { label: 'Download PDF', action: 'download', show: true },
    { label: 'Share Link', action: 'share', show: !!proposal.public_token },
    { label: 'Mark Complete', action: 'complete', show: proposal.status === 'signed' },
    {
      label: 'Decline',
      action: 'decline',
      show: ['sent', 'viewed', 'waiting_signature'].includes(proposal.status),
    },
    { label: 'Convert to Template', action: 'convert_template', show: true },
    { label: 'Delete', action: 'delete', show: true, danger: true },
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
// CreateProposalModal
// ---------------------------------------------------------------------------

function CreateProposalModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState('');
  const [contactId, setContactId] = useState('');

  const contactsQuery = useQuery({
    queryKey: ['contacts', { forProposalCreate: true }],
    queryFn: () => listContacts({ page_size: 200 }),
  });

  const contacts = contactsQuery.data?.data ?? [];

  const createMutation = useMutation({
    mutationFn: (data: { contact_id: string; title: string }) => createProposal(data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success('Proposal created');
      navigate(`/proposals/${result.data.id}/edit`);
    },
    onError: () => {
      toast.error('Failed to create proposal');
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
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">New Proposal</h2>
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
              Title
            </label>
            <input
              id="proposal-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Website Redesign Proposal"
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
              Contact
            </label>
            <select
              id="proposal-contact"
              value={contactId}
              onChange={(e) => setContactId(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">Select a contact...</option>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.company_name}
                  {c.contact_name ? ` (${c.contact_name})` : ''}
                </option>
              ))}
            </select>
            {contactsQuery.isLoading && (
              <p className="text-xs text-gray-400 mt-1">Loading contacts...</p>
            )}
          </div>
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || !title.trim() || !contactId}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {createMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
              Create
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
                  No proposals
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
                    {proposal.contact?.company_name ?? 'No contact'}
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
      toast.success('Proposal deleted');
    },
    onError: () => toast.error('Failed to delete proposal'),
  });

  const sendMutation = useMutation({
    mutationFn: sendProposal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success('Proposal sent');
    },
    onError: () => toast.error('Failed to send proposal'),
  });

  const cloneMutation = useMutation({
    mutationFn: cloneProposal,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success('Proposal cloned');
      navigate(`/proposals/${result.data.id}`);
    },
    onError: () => toast.error('Failed to clone proposal'),
  });

  const declineMutation = useMutation({
    mutationFn: declineProposal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success('Proposal declined');
    },
    onError: () => toast.error('Failed to decline proposal'),
  });

  const completeMutation = useMutation({
    mutationFn: completeProposal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposal-stats'] });
      toast.success('Proposal marked as complete');
    },
    onError: () => toast.error('Failed to complete proposal'),
  });

  const convertMutation = useMutation({
    mutationFn: convertToTemplate,
    onSuccess: () => {
      toast.success('Converted to template');
    },
    onError: () => toast.error('Failed to convert to template'),
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
              toast.success('Link copied to clipboard');
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
        case 'delete':
          if (window.confirm('Are you sure you want to delete this proposal?')) {
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
      label: 'Total',
      value: stats ? stats.total_proposals.toLocaleString() : '--',
      icon: FileText,
      iconColor: 'text-purple-600 dark:text-purple-400',
      iconBg: 'bg-purple-50 dark:bg-purple-900/30',
    },
    {
      label: 'Draft',
      value: stats ? stats.draft_count.toLocaleString() : '--',
      icon: FileText,
      iconColor: 'text-gray-600 dark:text-gray-400',
      iconBg: 'bg-gray-100 dark:bg-gray-800',
    },
    {
      label: 'Sent',
      value: stats ? stats.sent_count.toLocaleString() : '--',
      icon: Send,
      iconColor: 'text-blue-600 dark:text-blue-400',
      iconBg: 'bg-blue-50 dark:bg-blue-900/30',
    },
    {
      label: 'Viewed',
      value: stats ? stats.viewed_count.toLocaleString() : '--',
      icon: Eye,
      iconColor: 'text-yellow-600 dark:text-yellow-400',
      iconBg: 'bg-yellow-50 dark:bg-yellow-900/30',
    },
    {
      label: 'Signed',
      value: stats ? stats.signed_count.toLocaleString() : '--',
      icon: CheckCircle,
      iconColor: 'text-green-600 dark:text-green-400',
      iconBg: 'bg-green-50 dark:bg-green-900/30',
    },
    {
      label: 'Paid',
      value: stats ? stats.paid_count.toLocaleString() : '--',
      icon: DollarSign,
      iconColor: 'text-emerald-600 dark:text-emerald-400',
      iconBg: 'bg-emerald-50 dark:bg-emerald-900/30',
    },
    {
      label: 'Total Value',
      value: stats ? formatCurrency(stats.total_value) : '--',
      icon: DollarSign,
      iconColor: 'text-indigo-600 dark:text-indigo-400',
      iconBg: 'bg-indigo-50 dark:bg-indigo-900/30',
    },
    {
      label: 'Signed Value',
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
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Proposals</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Proposal
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
            placeholder="Search proposals..."
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
          placeholder="From"
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
          placeholder="To"
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
            List
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
            Kanban
          </button>
        </div>
      </div>

      {/* Loading */}
      {proposalsQuery.isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-500 dark:text-gray-400">Loading proposals...</span>
        </div>
      )}

      {/* Empty state */}
      {!proposalsQuery.isLoading && proposals.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="p-4 rounded-full bg-gray-100 dark:bg-gray-800 mb-4">
            <FileText className="w-8 h-8 text-gray-400 dark:text-gray-500" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">
            No proposals yet
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4 max-w-sm">
            Create your first proposal to start closing deals and tracking your pipeline.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm"
          >
            <Plus className="w-4 h-4" />
            New Proposal
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
                  Title
                </th>
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                  Contact
                </th>
                <th className="text-right px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                  Value
                </th>
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                  Status
                </th>
                <th className="text-left px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                  Created
                </th>
                <th className="text-right px-5 py-3 text-gray-500 dark:text-gray-400 font-medium">
                  Actions
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
            Page {meta.page} of {meta.total_pages} ({meta.total_count} total)
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= meta.total_pages}
              className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Create modal */}
      {showCreateModal && <CreateProposalModal onClose={() => setShowCreateModal(false)} />}
    </div>
  );
}
