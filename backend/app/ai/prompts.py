"""Prompt templates for AI-powered document extraction."""

RECEIPT_EXTRACTION_PROMPT = """Analyze this receipt or invoice image and extract all relevant information.

Return a JSON object with exactly these fields (use null for any field you cannot determine):

{
  "vendor_name": "string - the business/store name",
  "vendor_address": "string or null - the business address if visible",
  "date": "string - the transaction date in YYYY-MM-DD format",
  "currency": "string - three-letter currency code (e.g., USD, EUR, GBP)",
  "subtotal": number or null,
  "tax_amount": number or null,
  "tax_rate": number or null (as a percentage, e.g., 8.5 for 8.5%),
  "total_amount": number - the final total,
  "tip_amount": number or null,
  "payment_method": "string or null - e.g., cash, credit_card, debit_card, bank_transfer, check",
  "line_items": [
    {
      "description": "string - item name/description",
      "quantity": number or null,
      "unit_price": number or null,
      "total": number
    }
  ],
  "category": "string - best guess category from: food_dining, transportation, office_supplies, travel, utilities, insurance, professional_services, software_subscriptions, marketing, equipment, taxes, entertainment, healthcare, education, other",
  "receipt_number": "string or null - receipt/invoice number if visible",
  "full_text": "string - complete OCR text of the document, preserving line structure"
}

Important:
- All monetary values should be plain numbers (no currency symbols).
- Dates must be in YYYY-MM-DD format.
- If the image is not a receipt or invoice, still extract whatever financial information is visible.
- Return ONLY the JSON object, no additional text or markdown."""
