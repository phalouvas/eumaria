# Eumaria Gift Card Implementation Plan

## Overview
Implement a gift card system for a physiotherapy clinic where customers can purchase prepaid vouchers for recipients. The recipient can redeem the gift card when making payment for patient appointments.

## Business Requirements

### Core Features
1. **Gift Card Creation**: Create gift cards with unique voucher numbers
2. **Customer Assignment**: Link gift cards to recipient customers (patients)
3. **Validity Period**: 2-year default validity (Cyprus consumer protection compliance)
4. **Single Card Usage**: One gift card per appointment (no combination)
5. **Partial Redemptions**: Track remaining balance after partial use
6. **Expiry Management**: Automatic status update to "Expired" after expiry date
7. **Accounting Integration**: Proper advance payment and revenue recognition

### User Workflows
- **Purchase**: Staff creates gift card, receives payment, card becomes active
- **Redemption**: Patient selects gift card when paying for appointment
- **Management**: View active/expired/redeemed cards, check balances

## Accounting Principles

### Cyprus Compliance
- **VAT Treatment**: Multi-purpose voucher (VAT accounted at redemption, not issuance)
- **Validity**: Minimum 2-year validity (Cyprus/EU consumer protection)
- **Advance Accounting**: Gift cards are customer advances (liabilities)

### Company Settings Configuration
Before implementation, ensure these Company settings:
```
Book Advance Payments in Separate Party Account: ✅ ENABLED
Default Advance Received Account: Set to liability account (e.g., "2105 - Customer Advances")
Reconciliation Takes Effect On: "Advance Payment Date"
```

### Accounting Flow
1. **Gift Card Sale**:
   - Payment Entry (Receive) with "Is Advance = Yes"
   - Debit: Bank/Cash
   - Credit: Customer Advances (liability)

2. **Appointment Redemption**:
   - Sales Invoice created for appointment
   - Advance allocated from gift card's linked Payment Entry
   - ERPNext automatically:
     - Debits Customer Advances (reduces liability)
     - Credits Revenue (with correct VAT at redemption)

## Technical Implementation

### 1. Gift Card Doctype Structure

#### Fields Required:
- `voucher_number` (Data, unique, auto-generated)
- `purchaser_name` (Data - name of person buying the gift)
- `recipient_customer` (Link: Customer, mandatory)
- `start_date` (Date, default: today)
- `expiry_date` (Date, default: today + 2 years)
- `status` (Select: Draft/Active/Partially Redeemed/Redeemed/Expired/Cancelled)
- `initial_amount` (Currency, mandatory)
- `remaining_amount` (Currency, read-only)
- `linked_payment_entry` (Link: Payment Entry, read-only)
- `last_redemption_invoice` (Link: Sales Invoice, hidden, for tracking)

#### Doctype Behavior:
- **On Submit**:
  - Create Payment Entry with `is_advance = "Yes"`
  - Link Payment Entry to gift card
  - Set status to "Active"
  - Set `remaining_amount = initial_amount`
  
- **On Cancel**:
  - Cancel linked Payment Entry
  - Set status to "Cancelled"
  
- **Daily Cron Job**:
  - Mark gift cards as "Expired" when `expiry_date < today` and status is Active/Partially Redeemed

### 2. Patient Appointment Integration

#### Custom Field on Patient Appointment:
- Add `use_gift_card` (Check) field
- Add `selected_gift_card` (Link: Eumaria Gift Card) field (visible when checkbox checked)

#### Form Enhancement (patient_appointment.js):
- Add "Use Gift Card" checkbox
- When checked, show dropdown of active gift cards for the patient
- Filter gift cards by: `recipient_customer = patient`, `status in ("Active", "Partially Redeemed")`, `expiry_date >= today`
- Display remaining amount for selected gift card
- Validation: Show warning if appointment estimated cost > gift card remaining amount

### 3. Invoice Creation Override

#### Current Healthcare Flow:
Patient Appointment → "Make Payment" → Creates Sales Invoice + Payment Entry

#### Modified Flow with Gift Card:
1. User checks "Use Gift Card" and selects a card
2. Click "Make Payment"
3. **Instead of creating new Payment Entry**:
   - Create Sales Invoice normally
   - Allocate advance from gift card's `linked_payment_entry`
   - Use `remaining_amount` as maximum allocatable amount
4. Update gift card:
   - `remaining_amount = remaining_amount - allocated_amount`
   - If `remaining_amount == 0`: status = "Redeemed"
   - If `remaining_amount > 0`: status = "Partially Redeemed"
   - Set `last_redemption_invoice` to the new invoice

### 4. API Endpoints Required

#### For Frontend:
- `get_active_gift_cards_for_patient(patient_name)`: Returns active cards for dropdown
- `get_gift_card_balance(gift_card_name)`: Returns remaining amount

#### For Invoice Creation:
- `allocate_gift_card_to_invoice(gift_card_name, invoice_name, appointment_name)`: Links and updates

### 5. Scheduled Tasks
- **Daily**: `mark_expired_gift_cards()` - Update status of expired cards
- **Optional Monthly Report**: Outstanding gift card liabilities

## Integration Points

### With Existing Eumaria Features:
- **Group Sessions**: Gift cards work independently of group session flag
- **Body Map Annotation**: No interaction required
- **SMS Suppression**: Gift card redemption doesn't affect SMS flow

### With ERPNext Core:
- **Payment Entry**: Uses standard advance payment mechanism
- **Sales Invoice**: Uses standard advance allocation
- **Customer**: Links to customer record (patient's customer link)
- **Accounting**: Leverages ERPNext's automatic journal entries

## Implementation Steps

### Phase 1: Foundation
1. Create Gift Card doctype (JSON + Python controller)
2. Implement `on_submit` to create Payment Entry
3. Implement `on_cancel` to cancel Payment Entry
4. Add daily cron job for expiry management

### Phase 2: Patient Appointment Integration
1. Add custom fields to Patient Appointment doctype
2. Modify `patient_appointment.js` for gift card UI
3. Create API endpoints for frontend

### Phase 3: Invoice Creation Override
1. Identify where invoice creation happens in Healthcare module
2. Create wrapper/override function that checks for gift card
3. Implement advance allocation logic
4. Add gift card status update after redemption

### Phase 4: Testing & Validation
1. Test gift card creation and payment entry
2. Test appointment payment with gift card
3. Test partial redemption scenarios
4. Test expiry automation
5. Validate accounting entries

## Testing Scenarios

### Happy Paths:
1. **Full Redemption**: Appointment cost <= gift card balance
2. **Partial Redemption**: Appointment cost < gift card balance (leaves remainder)
3. **Multiple Appointments**: Use same gift card across multiple appointments until balance exhausted

### Edge Cases:
1. **Insufficient Balance**: Appointment cost > gift card balance (warning, manual payment for difference)
2. **Expired Card**: Attempt to use expired card (prevent selection)
3. **Cancelled Appointment**: What happens to allocated advance? (ERPNext handles unallocation)
4. **Invoice Cancellation**: Gift card balance should be restored

### Accounting Validation:
1. Verify Payment Entry created with `is_advance = "Yes"`
2. Verify Sales Invoice uses advance allocation (not new Payment Entry)
3. Verify Journal Entries show proper liability reduction
4. Verify VAT calculated at redemption (not at issuance)

## Important Notes

### Critical Requirements:
1. **Never use "Debtors" account** for gift cards - must use advance liability account
2. **Always check `is_advance = "Yes"`** when creating Payment Entry
3. **Default expiry must be 2 years** for Cyprus compliance
4. **Single card per appointment** - don't implement multiple card combination
5. **No automatic refunds** - manual process only if needed

### Security Considerations:
1. Gift cards should only be visible to authorized staff
2. Balance checks via API should validate user permissions
3. Payment Entry creation should respect accounting permissions

### Performance Considerations:
1. Index `recipient_customer`, `status`, `expiry_date` for fast filtering
2. Cache active gift cards for frequent patient lookups
3. Consider batch processing for daily expiry updates if large volume

## Success Criteria

### Functional:
- [ ] Gift cards can be created with unique voucher numbers
- [ ] Payment Entry created automatically on submission
- [ ] Patient Appointment shows gift card selection dropdown
- [ ] Invoice creation uses advance allocation instead of new payment
- [ ] Remaining balance tracked correctly
- [ ] Expired cards automatically marked
- [ ] Partial redemptions supported

### Accounting:
- [ ] Payment Entry has `is_advance = "Yes"`
- [ ] Sales Invoice allocates from advance correctly
- [ ] Journal Entries show proper liability→revenue movement
- [ ] VAT accounted at redemption (not issuance)

### User Experience:
- [ ] Clear warnings for insufficient balance
- [ ] Easy gift card selection in Patient Appointment
- [ ] Balance visibility before payment
- [ ] Status clearly displayed (Active/Partially Redeemed/etc.)

## Next Steps for Implementation Agent

1. **Review this document** thoroughly
2. **Examine existing codebase** to understand current Patient Appointment and invoice creation flow
3. **Start with Phase 1** (Gift Card doctype)
4. **Test accounting flow** with a Cyprus accountant if possible
5. **Implement incrementally** with testing after each phase
6. **Document any deviations** from this plan with rationale

Remember: This implementation leverages ERPNext's standard advance payment mechanisms - don't create custom journal entries unless absolutely necessary. The goal is to use existing accounting flows with minimal customization.