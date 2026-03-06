import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  ArrowLeft,
  Save,
  Send,
  Eye,
  EyeOff,
  GripVertical,
  X,
  Plus,
  Trash2,
  ChevronUp,
  ChevronDown,
  Type,
  ImageIcon,
  Video,
  Table,
  Tag,
  PenTool,
  Minus,
  UserPlus,
  Settings,
  Layers,
  DollarSign,
} from 'lucide-react';
import {
  getProposal,
  updateProposal,
  sendProposal,
  addRecipient,
  removeRecipient,
} from '@/api/proposals';
import type { Proposal, ProposalRecipient } from '@/api/proposals';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ContentBlock {
  id: string;
  type: 'text' | 'image' | 'video' | 'pricing_table' | 'custom_value' | 'signature' | 'page_break';
  data: Record<string, any>;
  order: number;
}

interface PricingItem {
  id: string;
  item: string;
  description: string;
  qty: number;
  rate: number;
  tax: number;
  discount: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BLOCK_TYPES = [
  { type: 'text' as const, label: 'Text', icon: Type },
  { type: 'image' as const, label: 'Image', icon: ImageIcon },
  { type: 'video' as const, label: 'Video', icon: Video },
  { type: 'pricing_table' as const, label: 'Pricing Table', icon: Table },
  { type: 'custom_value' as const, label: 'Custom Value', icon: Tag },
  { type: 'signature' as const, label: 'Signature', icon: PenTool },
  { type: 'page_break' as const, label: 'Page Break', icon: Minus },
];

const MERGE_FIELDS = [
  { value: '{{contact.name}}', label: 'Contact Name' },
  { value: '{{contact.email}}', label: 'Contact Email' },
  { value: '{{contact.company}}', label: 'Contact Company' },
  { value: '{{contact.address}}', label: 'Contact Address' },
];

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300',
  sent: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300',
  viewed: 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300',
  waiting_signature: 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300',
  signed: 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300',
  declined: 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300',
  paid: 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300',
};

const formatCurrency = (amount: number, currency = 'USD') =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);

// ---------------------------------------------------------------------------
// Helper: create a default block
// ---------------------------------------------------------------------------

function createBlock(type: ContentBlock['type'], order: number): ContentBlock {
  const id = crypto.randomUUID();
  const base = { id, type, order };

  switch (type) {
    case 'text':
      return { ...base, data: { html: '' } };
    case 'image':
      return { ...base, data: { url: '', alt: '' } };
    case 'video':
      return { ...base, data: { url: '' } };
    case 'pricing_table':
      return {
        ...base,
        data: {
          items: [
            { id: crypto.randomUUID(), item: '', description: '', qty: 1, rate: 0, tax: 0, discount: 0 },
          ],
          subtotal: 0,
          tax_total: 0,
          discount_total: 0,
          grand_total: 0,
        },
      };
    case 'custom_value':
      return { ...base, data: { field: '{{contact.name}}' } };
    case 'signature':
      return { ...base, data: { recipient_id: '', label: 'Signature' } };
    case 'page_break':
      return { ...base, data: {} };
    default:
      return { ...base, data: {} };
  }
}

// ---------------------------------------------------------------------------
// Helper: parse video embed URL
// ---------------------------------------------------------------------------

function getEmbedUrl(url: string): string | null {
  if (!url) return null;
  // YouTube
  const ytMatch = url.match(
    /(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/
  );
  if (ytMatch) return `https://www.youtube.com/embed/${ytMatch[1]}`;
  // Vimeo
  const vimeoMatch = url.match(/vimeo\.com\/(\d+)/);
  if (vimeoMatch) return `https://player.vimeo.com/video/${vimeoMatch[1]}`;
  return null;
}

// ---------------------------------------------------------------------------
// Sub-component: TextBlockEditor
// ---------------------------------------------------------------------------

function TextBlockEditor({
  block,
  preview,
  onChange,
}: {
  block: ContentBlock;
  preview: boolean;
  onChange: (data: Record<string, any>) => void;
}) {
  if (preview) {
    return (
      <div
        className="prose dark:prose-invert max-w-none text-sm"
        dangerouslySetInnerHTML={{ __html: block.data.html || '<p class="text-gray-400">Empty text block</p>' }}
      />
    );
  }

  return (
    <textarea
      value={block.data.html || ''}
      onChange={(e) => onChange({ html: e.target.value })}
      placeholder="Enter text content (supports HTML)..."
      rows={4}
      className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
    />
  );
}

// ---------------------------------------------------------------------------
// Sub-component: ImageBlockEditor
// ---------------------------------------------------------------------------

function ImageBlockEditor({
  block,
  preview,
  onChange,
}: {
  block: ContentBlock;
  preview: boolean;
  onChange: (data: Record<string, any>) => void;
}) {
  if (preview) {
    if (!block.data.url) {
      return <div className="text-sm text-gray-400 italic">No image set</div>;
    }
    return (
      <div className="flex justify-center">
        <img
          src={block.data.url}
          alt={block.data.alt || ''}
          className="max-w-full max-h-96 rounded-lg object-contain"
        />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
          Image URL
        </label>
        <input
          type="url"
          value={block.data.url || ''}
          onChange={(e) => onChange({ ...block.data, url: e.target.value })}
          placeholder="https://example.com/image.jpg"
          className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
          Alt Text
        </label>
        <input
          type="text"
          value={block.data.alt || ''}
          onChange={(e) => onChange({ ...block.data, alt: e.target.value })}
          placeholder="Describe the image..."
          className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
      {block.data.url && (
        <div className="flex justify-center pt-2">
          <img
            src={block.data.url}
            alt={block.data.alt || ''}
            className="max-w-full max-h-48 rounded-lg object-contain border border-gray-200 dark:border-gray-700"
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: VideoBlockEditor
// ---------------------------------------------------------------------------

function VideoBlockEditor({
  block,
  preview,
  onChange,
}: {
  block: ContentBlock;
  preview: boolean;
  onChange: (data: Record<string, any>) => void;
}) {
  const embedUrl = getEmbedUrl(block.data.url || '');

  if (preview) {
    if (!embedUrl) {
      return <div className="text-sm text-gray-400 italic">No video set</div>;
    }
    return (
      <div className="aspect-video w-full max-w-2xl mx-auto">
        <iframe
          src={embedUrl}
          className="w-full h-full rounded-lg"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          title="Embedded video"
        />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
          Video URL (YouTube or Vimeo)
        </label>
        <input
          type="url"
          value={block.data.url || ''}
          onChange={(e) => onChange({ url: e.target.value })}
          placeholder="https://www.youtube.com/watch?v=..."
          className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
      {embedUrl && (
        <div className="aspect-video w-full max-w-lg mx-auto">
          <iframe
            src={embedUrl}
            className="w-full h-full rounded-lg"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            title="Embedded video preview"
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: PricingTableEditor
// ---------------------------------------------------------------------------

function PricingTableEditor({
  block,
  preview,
  onChange,
}: {
  block: ContentBlock;
  preview: boolean;
  onChange: (data: Record<string, any>) => void;
}) {
  const items: PricingItem[] = block.data.items || [];

  const recalculate = useCallback(
    (updatedItems: PricingItem[]) => {
      let subtotal = 0;
      let taxTotal = 0;
      let discountTotal = 0;

      for (const row of updatedItems) {
        const lineBase = row.qty * row.rate;
        const lineTax = lineBase * (row.tax / 100);
        const lineDiscount = lineBase * (row.discount / 100);
        subtotal += lineBase;
        taxTotal += lineTax;
        discountTotal += lineDiscount;
      }

      const grandTotal = subtotal + taxTotal - discountTotal;
      onChange({
        items: updatedItems,
        subtotal,
        tax_total: taxTotal,
        discount_total: discountTotal,
        grand_total: grandTotal,
      });
    },
    [onChange]
  );

  const updateItem = (itemId: string, field: keyof PricingItem, value: string | number) => {
    const updated = items.map((it) => (it.id === itemId ? { ...it, [field]: value } : it));
    recalculate(updated);
  };

  const addRow = () => {
    const newItem: PricingItem = {
      id: crypto.randomUUID(),
      item: '',
      description: '',
      qty: 1,
      rate: 0,
      tax: 0,
      discount: 0,
    };
    recalculate([...items, newItem]);
  };

  const removeRow = (itemId: string) => {
    recalculate(items.filter((it) => it.id !== itemId));
  };

  const lineTotal = (row: PricingItem) => {
    const base = row.qty * row.rate;
    return base + base * (row.tax / 100) - base * (row.discount / 100);
  };

  if (preview) {
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <th className="text-left px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Item</th>
              <th className="text-left px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Description</th>
              <th className="text-right px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Qty</th>
              <th className="text-right px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Rate</th>
              <th className="text-right px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Tax%</th>
              <th className="text-right px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Disc%</th>
              <th className="text-right px-3 py-2 text-gray-500 dark:text-gray-400 font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.id} className="border-b border-gray-100 dark:border-gray-800">
                <td className="px-3 py-2 text-gray-900 dark:text-gray-100">{row.item || '-'}</td>
                <td className="px-3 py-2 text-gray-600 dark:text-gray-400">{row.description || '-'}</td>
                <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100">{row.qty}</td>
                <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100">{formatCurrency(row.rate)}</td>
                <td className="px-3 py-2 text-right text-gray-500 dark:text-gray-400">{row.tax}%</td>
                <td className="px-3 py-2 text-right text-gray-500 dark:text-gray-400">{row.discount}%</td>
                <td className="px-3 py-2 text-right font-medium text-gray-900 dark:text-gray-100">
                  {formatCurrency(lineTotal(row))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex flex-col items-end mt-3 space-y-1">
          <div className="flex justify-between w-56 text-sm">
            <span className="text-gray-500 dark:text-gray-400">Subtotal</span>
            <span className="text-gray-900 dark:text-gray-100">{formatCurrency(block.data.subtotal || 0)}</span>
          </div>
          <div className="flex justify-between w-56 text-sm">
            <span className="text-gray-500 dark:text-gray-400">Tax</span>
            <span className="text-gray-900 dark:text-gray-100">{formatCurrency(block.data.tax_total || 0)}</span>
          </div>
          <div className="flex justify-between w-56 text-sm">
            <span className="text-gray-500 dark:text-gray-400">Discount</span>
            <span className="text-red-500">-{formatCurrency(block.data.discount_total || 0)}</span>
          </div>
          <div className="flex justify-between w-56 text-sm pt-1 border-t border-gray-200 dark:border-gray-700 mt-1">
            <span className="font-medium text-gray-900 dark:text-gray-100">Grand Total</span>
            <span className="font-semibold text-gray-900 dark:text-gray-100">
              {formatCurrency(block.data.grand_total || 0)}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <th className="text-left px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">Item</th>
              <th className="text-left px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">Description</th>
              <th className="text-right px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 w-16">Qty</th>
              <th className="text-right px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 w-24">Rate</th>
              <th className="text-right px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 w-16">Tax%</th>
              <th className="text-right px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 w-16">Disc%</th>
              <th className="text-right px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 w-24">Total</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.id} className="border-b border-gray-100 dark:border-gray-800">
                <td className="px-2 py-1.5">
                  <input
                    type="text"
                    value={row.item}
                    onChange={(e) => updateItem(row.id, 'item', e.target.value)}
                    placeholder="Item name"
                    className="w-full px-2 py-1 text-sm border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    type="text"
                    value={row.description}
                    onChange={(e) => updateItem(row.id, 'description', e.target.value)}
                    placeholder="Description"
                    className="w-full px-2 py-1 text-sm border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={row.qty}
                    onChange={(e) => updateItem(row.id, 'qty', parseFloat(e.target.value) || 0)}
                    className="w-full px-2 py-1 text-sm text-right border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={row.rate}
                    onChange={(e) => updateItem(row.id, 'rate', parseFloat(e.target.value) || 0)}
                    className="w-full px-2 py-1 text-sm text-right border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={0.1}
                    value={row.tax}
                    onChange={(e) => updateItem(row.id, 'tax', parseFloat(e.target.value) || 0)}
                    className="w-full px-2 py-1 text-sm text-right border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={0.1}
                    value={row.discount}
                    onChange={(e) => updateItem(row.id, 'discount', parseFloat(e.target.value) || 0)}
                    className="w-full px-2 py-1 text-sm text-right border border-gray-200 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                <td className="px-2 py-1.5 text-right text-sm font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">
                  {formatCurrency(lineTotal(row))}
                </td>
                <td className="px-1 py-1.5">
                  <button
                    onClick={() => removeRow(row.id)}
                    className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                    title="Remove row"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button
        onClick={addRow}
        className="flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
      >
        <Plus className="w-3.5 h-3.5" />
        Add Row
      </button>

      <div className="flex flex-col items-end space-y-1 text-sm">
        <div className="flex justify-between w-56">
          <span className="text-gray-500 dark:text-gray-400">Subtotal</span>
          <span className="text-gray-900 dark:text-gray-100">{formatCurrency(block.data.subtotal || 0)}</span>
        </div>
        <div className="flex justify-between w-56">
          <span className="text-gray-500 dark:text-gray-400">Tax</span>
          <span className="text-gray-900 dark:text-gray-100">{formatCurrency(block.data.tax_total || 0)}</span>
        </div>
        <div className="flex justify-between w-56">
          <span className="text-gray-500 dark:text-gray-400">Discount</span>
          <span className="text-red-500">-{formatCurrency(block.data.discount_total || 0)}</span>
        </div>
        <div className="flex justify-between w-56 pt-1 border-t border-gray-200 dark:border-gray-700 mt-1">
          <span className="font-medium text-gray-900 dark:text-gray-100">Grand Total</span>
          <span className="font-semibold text-gray-900 dark:text-gray-100">
            {formatCurrency(block.data.grand_total || 0)}
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: CustomValueEditor
// ---------------------------------------------------------------------------

function CustomValueEditor({
  block,
  preview,
  onChange,
}: {
  block: ContentBlock;
  preview: boolean;
  onChange: (data: Record<string, any>) => void;
}) {
  const selected = MERGE_FIELDS.find((f) => f.value === block.data.field);

  if (preview) {
    return (
      <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 text-sm font-medium">
        <Tag className="w-3.5 h-3.5" />
        {selected?.label || block.data.field}
      </span>
    );
  }

  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
        Merge Field
      </label>
      <select
        value={block.data.field || '{{contact.name}}'}
        onChange={(e) => onChange({ field: e.target.value })}
        className="w-full max-w-xs px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      >
        {MERGE_FIELDS.map((f) => (
          <option key={f.value} value={f.value}>
            {f.label} ({f.value})
          </option>
        ))}
      </select>
      <div className="mt-2">
        <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 text-sm font-medium">
          <Tag className="w-3.5 h-3.5" />
          {selected?.label || block.data.field}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: SignatureBlockEditor
// ---------------------------------------------------------------------------

function SignatureBlockEditor({
  block,
  preview,
  recipients,
  onChange,
}: {
  block: ContentBlock;
  preview: boolean;
  recipients: ProposalRecipient[];
  onChange: (data: Record<string, any>) => void;
}) {
  if (preview) {
    const assigned = recipients.find((r) => r.id === block.data.recipient_id);
    return (
      <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center">
        <PenTool className="w-6 h-6 mx-auto text-gray-400 dark:text-gray-500 mb-2" />
        <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
          {block.data.label || 'Signature'}
        </p>
        {assigned && (
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            {assigned.name} ({assigned.email})
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
          Label
        </label>
        <input
          type="text"
          value={block.data.label || ''}
          onChange={(e) => onChange({ ...block.data, label: e.target.value })}
          placeholder="Signature"
          className="w-full max-w-xs px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
          Assigned Recipient
        </label>
        <select
          value={block.data.recipient_id || ''}
          onChange={(e) => onChange({ ...block.data, recipient_id: e.target.value })}
          className="w-full max-w-xs px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          <option value="">-- Select recipient --</option>
          {recipients.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name} ({r.email})
            </option>
          ))}
        </select>
      </div>
      <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center">
        <PenTool className="w-6 h-6 mx-auto text-gray-400 dark:text-gray-500 mb-2" />
        <p className="text-sm text-gray-500 dark:text-gray-400">{block.data.label || 'Signature'} placeholder</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: PageBreakBlock
// ---------------------------------------------------------------------------

function PageBreakBlock({ preview: _preview }: { preview: boolean }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <div className="flex-1 border-t border-gray-300 dark:border-gray-600 border-dashed" />
      <span className="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider">
        Page Break
      </span>
      <div className="flex-1 border-t border-gray-300 dark:border-gray-600 border-dashed" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: BlockRenderer
// ---------------------------------------------------------------------------

function BlockRenderer({
  block,
  preview,
  recipients,
  isFirst,
  isLast,
  onUpdate,
  onDelete,
  onMoveUp,
  onMoveDown,
}: {
  block: ContentBlock;
  preview: boolean;
  recipients: ProposalRecipient[];
  isFirst: boolean;
  isLast: boolean;
  onUpdate: (data: Record<string, any>) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const blockTypeInfo = BLOCK_TYPES.find((bt) => bt.type === block.type);
  const Icon = blockTypeInfo?.icon || Type;

  return (
    <div
      className={cn(
        'group relative border rounded-xl transition-colors',
        preview
          ? 'border-transparent'
          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 bg-white dark:bg-gray-900'
      )}
    >
      {/* Block header (edit mode only) */}
      {!preview && (
        <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2">
            <GripVertical className="w-4 h-4 text-gray-300 dark:text-gray-600" />
            <Icon className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
              {blockTypeInfo?.label || block.type}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={onMoveUp}
              disabled={isFirst}
              className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Move up"
            >
              <ChevronUp className="w-4 h-4" />
            </button>
            <button
              onClick={onMoveDown}
              disabled={isLast}
              className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Move down"
            >
              <ChevronDown className="w-4 h-4" />
            </button>
            <button
              onClick={onDelete}
              className="p-1 text-gray-400 hover:text-red-500 transition-colors"
              title="Delete block"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Block content */}
      <div className={cn('px-4', preview ? 'py-2' : 'py-3')}>
        {block.type === 'text' && (
          <TextBlockEditor block={block} preview={preview} onChange={onUpdate} />
        )}
        {block.type === 'image' && (
          <ImageBlockEditor block={block} preview={preview} onChange={onUpdate} />
        )}
        {block.type === 'video' && (
          <VideoBlockEditor block={block} preview={preview} onChange={onUpdate} />
        )}
        {block.type === 'pricing_table' && (
          <PricingTableEditor block={block} preview={preview} onChange={onUpdate} />
        )}
        {block.type === 'custom_value' && (
          <CustomValueEditor block={block} preview={preview} onChange={onUpdate} />
        )}
        {block.type === 'signature' && (
          <SignatureBlockEditor
            block={block}
            preview={preview}
            recipients={recipients}
            onChange={onUpdate}
          />
        )}
        {block.type === 'page_break' && <PageBreakBlock preview={preview} />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: RecipientManager
// ---------------------------------------------------------------------------

function RecipientManager({
  proposalId,
  recipients,
  isDraft,
}: {
  proposalId: string;
  recipients: ProposalRecipient[];
  isDraft: boolean;
}) {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newName, setNewName] = useState('');
  const [newRole, setNewRole] = useState('signer');

  const addMutation = useMutation({
    mutationFn: (data: { email: string; name: string; role: string }) =>
      addRecipient(proposalId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposal', proposalId] });
      setNewEmail('');
      setNewName('');
      setNewRole('signer');
      setShowAdd(false);
      toast.success('Recipient added');
    },
    onError: () => toast.error('Failed to add recipient'),
  });

  const removeMutation = useMutation({
    mutationFn: (recipientId: string) => removeRecipient(proposalId, recipientId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposal', proposalId] });
      toast.success('Recipient removed');
    },
    onError: () => toast.error('Failed to remove recipient'),
  });

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim() || !newName.trim()) return;
    addMutation.mutate({ email: newEmail.trim(), name: newName.trim(), role: newRole });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Recipients</h3>
        {isDraft && (
          <button
            onClick={() => setShowAdd(!showAdd)}
            className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
          >
            <UserPlus className="w-3.5 h-3.5" />
            Add
          </button>
        )}
      </div>

      {recipients.length === 0 && (
        <p className="text-xs text-gray-400 dark:text-gray-500 italic">No recipients yet</p>
      )}

      {recipients.map((r) => (
        <div
          key={r.id}
          className="flex items-start justify-between gap-2 p-2 rounded-lg bg-gray-50 dark:bg-gray-800/50"
        >
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{r.name}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{r.email}</p>
            <span className="text-xs text-gray-400 dark:text-gray-500 capitalize">{r.role}</span>
          </div>
          {isDraft && (
            <button
              onClick={() => removeMutation.mutate(r.id)}
              disabled={removeMutation.isPending}
              className="p-1 text-gray-400 hover:text-red-500 transition-colors shrink-0"
              title="Remove recipient"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      ))}

      {showAdd && isDraft && (
        <form onSubmit={handleAdd} className="space-y-2 p-3 border border-gray-200 dark:border-gray-700 rounded-lg">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Name"
            required
            className="w-full px-2.5 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="Email"
            required
            className="w-full px-2.5 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <select
            value={newRole}
            onChange={(e) => setNewRole(e.target.value)}
            className="w-full px-2.5 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="signer">Signer</option>
            <option value="viewer">Viewer</option>
            <option value="approver">Approver</option>
          </select>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={addMutation.isPending}
              className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {addMutation.isPending ? 'Adding...' : 'Add'}
            </button>
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="px-3 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function ProposalEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // State
  const [blocks, setBlocks] = useState<ContentBlock[]>([]);
  const [title, setTitle] = useState('');
  const [editingTitle, setEditingTitle] = useState(false);
  const [preview, setPreview] = useState(false);

  // Settings state
  const [collectPayment, setCollectPayment] = useState(false);
  const [paymentMode, setPaymentMode] = useState<string>('one-time');
  const [paymentFrequency, setPaymentFrequency] = useState<string>('monthly');
  const [followUpEnabled, setFollowUpEnabled] = useState(false);
  const [followUpHours, setFollowUpHours] = useState(24);
  const [manualValue, setManualValue] = useState<number | null>(null);

  // Refs
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialLoadDoneRef = useRef(false);
  const titleInputRef = useRef<HTMLInputElement>(null);

  // ---- Query: load proposal ----
  const proposalQuery = useQuery({
    queryKey: ['proposal', id],
    queryFn: () => getProposal(id!),
    enabled: !!id,
  });

  const proposal: Proposal | undefined = proposalQuery.data?.data;

  // ---- Initialize state from fetched proposal ----
  useEffect(() => {
    if (!proposal || initialLoadDoneRef.current) return;
    initialLoadDoneRef.current = true;

    setTitle(proposal.title);
    setCollectPayment(proposal.collect_payment);
    setPaymentMode(proposal.payment_mode || 'one-time');
    setPaymentFrequency(proposal.payment_frequency || 'monthly');
    setFollowUpEnabled(proposal.follow_up_enabled);
    setFollowUpHours(proposal.follow_up_hours || 24);

    try {
      const parsed = JSON.parse(proposal.content_json || '[]');
      if (Array.isArray(parsed)) {
        setBlocks(parsed);
      }
    } catch {
      setBlocks([]);
    }
  }, [proposal]);

  // ---- Computed values ----
  const isDraft = proposal?.status === 'draft';

  const computedValue = useMemo(() => {
    let total = 0;
    for (const block of blocks) {
      if (block.type === 'pricing_table' && block.data.grand_total) {
        total += block.data.grand_total;
      }
    }
    return total;
  }, [blocks]);

  const displayValue = manualValue !== null ? manualValue : computedValue;

  // ---- Save mutation ----
  const saveMutation = useMutation({
    mutationFn: (data: Partial<Proposal>) => updateProposal(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposal', id] });
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
    },
    onError: () => toast.error('Failed to save proposal'),
  });

  // ---- Send mutation ----
  const sendMutation = useMutation({
    mutationFn: () => sendProposal(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposal', id] });
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      toast.success('Proposal sent successfully');
    },
    onError: () => toast.error('Failed to send proposal'),
  });

  // ---- Debounced auto-save ----
  const triggerAutoSave = useCallback(
    (updatedBlocks: ContentBlock[]) => {
      if (!id || !initialLoadDoneRef.current) return;
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
      autoSaveTimerRef.current = setTimeout(() => {
        saveMutation.mutate({
          content_json: JSON.stringify(updatedBlocks),
          value: computedValue || undefined,
        });
      }, 500);
    },
    [id, saveMutation, computedValue]
  );

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, []);

  // ---- Block operations ----
  const addBlock = useCallback(
    (type: ContentBlock['type']) => {
      const newBlock = createBlock(type, blocks.length);
      const updated = [...blocks, newBlock];
      setBlocks(updated);
      triggerAutoSave(updated);
    },
    [blocks, triggerAutoSave]
  );

  const updateBlock = useCallback(
    (blockId: string, data: Record<string, any>) => {
      const updated = blocks.map((b) => (b.id === blockId ? { ...b, data } : b));
      setBlocks(updated);
      triggerAutoSave(updated);
    },
    [blocks, triggerAutoSave]
  );

  const deleteBlock = useCallback(
    (blockId: string) => {
      const filtered = blocks.filter((b) => b.id !== blockId);
      const reordered = filtered.map((b, i) => ({ ...b, order: i }));
      setBlocks(reordered);
      triggerAutoSave(reordered);
    },
    [blocks, triggerAutoSave]
  );

  const moveBlock = useCallback(
    (blockId: string, direction: 'up' | 'down') => {
      const index = blocks.findIndex((b) => b.id === blockId);
      if (index < 0) return;
      const swapIndex = direction === 'up' ? index - 1 : index + 1;
      if (swapIndex < 0 || swapIndex >= blocks.length) return;

      const newBlocks = [...blocks];
      [newBlocks[index], newBlocks[swapIndex]] = [newBlocks[swapIndex], newBlocks[index]];
      const reordered = newBlocks.map((b, i) => ({ ...b, order: i }));
      setBlocks(reordered);
      triggerAutoSave(reordered);
    },
    [blocks, triggerAutoSave]
  );

  // ---- Manual save (title + settings + content) ----
  const handleSave = useCallback(() => {
    if (!id) return;
    saveMutation.mutate({
      title,
      content_json: JSON.stringify(blocks),
      collect_payment: collectPayment,
      payment_mode: collectPayment ? paymentMode : null,
      payment_frequency: collectPayment && paymentMode === 'recurring' ? paymentFrequency : null,
      follow_up_enabled: followUpEnabled,
      follow_up_hours: followUpEnabled ? followUpHours : 0,
      value: manualValue !== null ? manualValue : computedValue,
    });
    toast.success('Proposal saved');
  }, [
    id,
    title,
    blocks,
    collectPayment,
    paymentMode,
    paymentFrequency,
    followUpEnabled,
    followUpHours,
    manualValue,
    computedValue,
    saveMutation,
  ]);

  // ---- Send handler ----
  const handleSend = useCallback(() => {
    if (!isDraft) return;
    // Save first, then send
    saveMutation.mutate(
      {
        title,
        content_json: JSON.stringify(blocks),
        collect_payment: collectPayment,
        payment_mode: collectPayment ? paymentMode : null,
        payment_frequency: collectPayment && paymentMode === 'recurring' ? paymentFrequency : null,
        follow_up_enabled: followUpEnabled,
        follow_up_hours: followUpEnabled ? followUpHours : 0,
        value: manualValue !== null ? manualValue : computedValue,
      },
      {
        onSuccess: () => {
          sendMutation.mutate();
        },
      }
    );
  }, [
    isDraft,
    title,
    blocks,
    collectPayment,
    paymentMode,
    paymentFrequency,
    followUpEnabled,
    followUpHours,
    manualValue,
    computedValue,
    saveMutation,
    sendMutation,
  ]);

  // ---- Focus title input on edit ----
  useEffect(() => {
    if (editingTitle && titleInputRef.current) {
      titleInputRef.current.focus();
      titleInputRef.current.select();
    }
  }, [editingTitle]);

  // ---- Loading / error states ----
  if (proposalQuery.isLoading) {
    return (
      <div className="flex items-center justify-center h-full p-12">
        <p className="text-gray-400 dark:text-gray-500">Loading proposal...</p>
      </div>
    );
  }

  if (proposalQuery.isError || !proposal) {
    return (
      <div className="p-6">
        <p className="text-red-500">Failed to load proposal.</p>
        <button
          onClick={() => navigate('/proposals')}
          className="mt-2 text-blue-600 dark:text-blue-400 hover:underline text-sm"
        >
          Back to Proposals
        </button>
      </div>
    );
  }

  // ---- Render ----
  return (
    <div className="flex flex-col h-full">
      {/* ================================================================ */}
      {/* Top Bar                                                          */}
      {/* ================================================================ */}
      <div className="shrink-0 flex items-center justify-between gap-4 px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        {/* Left: back + title + status */}
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => navigate('/proposals')}
            className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
            title="Back to Proposals"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>

          {editingTitle ? (
            <input
              ref={titleInputRef}
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={() => setEditingTitle(false)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') setEditingTitle(false);
                if (e.key === 'Escape') {
                  setTitle(proposal.title);
                  setEditingTitle(false);
                }
              }}
              className="text-lg font-semibold text-gray-900 dark:text-gray-100 bg-transparent border-b-2 border-blue-500 focus:outline-none min-w-0 w-64"
            />
          ) : (
            <button
              onClick={() => setEditingTitle(true)}
              className="text-lg font-semibold text-gray-900 dark:text-gray-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors truncate max-w-md"
              title="Click to edit title"
            >
              {title || 'Untitled Proposal'}
            </button>
          )}

          <span
            className={cn(
              'text-xs px-2 py-0.5 rounded-full font-medium whitespace-nowrap',
              STATUS_COLORS[proposal.status] || STATUS_COLORS.draft
            )}
          >
            {proposal.status.replace('_', ' ')}
          </span>
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setPreview(!preview)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border transition-colors',
              preview
                ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300'
                : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800'
            )}
          >
            {preview ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            {preview ? 'Edit' : 'Preview'}
          </button>

          <button
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 rounded-lg hover:bg-gray-800 dark:hover:bg-gray-200 disabled:opacity-50 transition-colors"
          >
            <Save className="w-4 h-4" />
            {saveMutation.isPending ? 'Saving...' : 'Save'}
          </button>

          {isDraft && (
            <button
              onClick={handleSend}
              disabled={sendMutation.isPending || saveMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <Send className="w-4 h-4" />
              {sendMutation.isPending ? 'Sending...' : 'Send'}
            </button>
          )}
        </div>
      </div>

      {/* ================================================================ */}
      {/* Body: sidebar + editor + settings                                */}
      {/* ================================================================ */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* ---- Left Sidebar: Block Palette ---- */}
        {!preview && (
          <div className="shrink-0 w-52 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 overflow-y-auto">
            <div className="p-3">
              <div className="flex items-center gap-2 mb-3">
                <Layers className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  Blocks
                </h3>
              </div>
              <div className="space-y-1">
                {BLOCK_TYPES.map((bt) => {
                  const Icon = bt.icon;
                  return (
                    <button
                      key={bt.type}
                      onClick={() => addBlock(bt.type)}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 rounded-lg hover:bg-white dark:hover:bg-gray-800 hover:shadow-sm border border-transparent hover:border-gray-200 dark:hover:border-gray-700 transition-all"
                    >
                      <Icon className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                      {bt.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ---- Main Editor Area ---- */}
        <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-950">
          <div className={cn('max-w-4xl mx-auto p-6', preview && 'max-w-3xl')}>
            {blocks.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <Layers className="w-12 h-12 text-gray-300 dark:text-gray-700 mb-4" />
                <p className="text-gray-500 dark:text-gray-400 text-sm mb-2">
                  No content blocks yet
                </p>
                <p className="text-gray-400 dark:text-gray-500 text-xs">
                  {preview
                    ? 'Switch to edit mode to add content blocks'
                    : 'Click a block type from the left sidebar to add content'}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {blocks
                  .sort((a, b) => a.order - b.order)
                  .map((block, index) => (
                    <BlockRenderer
                      key={block.id}
                      block={block}
                      preview={preview}
                      recipients={proposal.recipients}
                      isFirst={index === 0}
                      isLast={index === blocks.length - 1}
                      onUpdate={(data) => updateBlock(block.id, data)}
                      onDelete={() => deleteBlock(block.id)}
                      onMoveUp={() => moveBlock(block.id, 'up')}
                      onMoveDown={() => moveBlock(block.id, 'down')}
                    />
                  ))}
              </div>
            )}

            {/* Quick add button at bottom */}
            {!preview && blocks.length > 0 && (
              <div className="mt-6 flex justify-center">
                <div className="relative group">
                  <button className="flex items-center gap-1.5 text-sm text-gray-400 dark:text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors px-3 py-2 rounded-lg border border-dashed border-gray-300 dark:border-gray-700 hover:border-blue-400 dark:hover:border-blue-600">
                    <Plus className="w-4 h-4" />
                    Add block
                  </button>
                  {/* Dropdown on hover */}
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-20">
                    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-1 min-w-[160px]">
                      {BLOCK_TYPES.map((bt) => {
                        const Icon = bt.icon;
                        return (
                          <button
                            key={bt.type}
                            onClick={() => addBlock(bt.type)}
                            className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                          >
                            <Icon className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
                            {bt.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ---- Right Sidebar: Settings ---- */}
        <div className="shrink-0 w-72 border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-y-auto">
          <div className="p-4 space-y-6">
            {/* Settings header */}
            <div className="flex items-center gap-2">
              <Settings className="w-4 h-4 text-gray-400 dark:text-gray-500" />
              <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Settings
              </h3>
            </div>

            {/* Recipients */}
            <RecipientManager
              proposalId={id!}
              recipients={proposal.recipients}
              isDraft={isDraft}
            />

            <hr className="border-gray-100 dark:border-gray-800" />

            {/* Value */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <DollarSign className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Value</h3>
              </div>
              {computedValue > 0 && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Auto-calculated: {formatCurrency(computedValue, proposal.currency)}
                </p>
              )}
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                  {computedValue > 0 ? 'Override value' : 'Manual value'}
                </label>
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  value={manualValue ?? ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    setManualValue(val === '' ? null : parseFloat(val) || 0);
                  }}
                  placeholder={computedValue > 0 ? formatCurrency(computedValue) : '0.00'}
                  className="w-full px-2.5 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                Total: {formatCurrency(displayValue, proposal.currency)}
              </p>
            </div>

            <hr className="border-gray-100 dark:border-gray-800" />

            {/* Payment */}
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Payment</h3>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={collectPayment}
                  onChange={(e) => setCollectPayment(e.target.checked)}
                  className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Collect payment on signature
                </span>
              </label>

              {collectPayment && (
                <div className="space-y-2 pl-6">
                  <div>
                    <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                      Payment Mode
                    </label>
                    <select
                      value={paymentMode}
                      onChange={(e) => setPaymentMode(e.target.value)}
                      className="w-full px-2.5 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    >
                      <option value="one-time">One-time</option>
                      <option value="recurring">Recurring</option>
                    </select>
                  </div>

                  {paymentMode === 'recurring' && (
                    <div>
                      <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                        Frequency
                      </label>
                      <select
                        value={paymentFrequency}
                        onChange={(e) => setPaymentFrequency(e.target.value)}
                        className="w-full px-2.5 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="weekly">Weekly</option>
                        <option value="biweekly">Bi-weekly</option>
                        <option value="monthly">Monthly</option>
                        <option value="quarterly">Quarterly</option>
                        <option value="annually">Annually</option>
                      </select>
                    </div>
                  )}
                </div>
              )}
            </div>

            <hr className="border-gray-100 dark:border-gray-800" />

            {/* Follow-up */}
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Follow-up</h3>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={followUpEnabled}
                  onChange={(e) => setFollowUpEnabled(e.target.checked)}
                  className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Send follow-up if not signed
                </span>
              </label>

              {followUpEnabled && (
                <div className="pl-6">
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                    Hours after sending
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={followUpHours}
                    onChange={(e) => setFollowUpHours(parseInt(e.target.value) || 24)}
                    className="w-full px-2.5 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
