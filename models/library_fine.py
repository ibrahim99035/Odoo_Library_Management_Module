from odoo import models, fields, api
from odoo.exceptions import ValidationError
from  datetime import timedelta
class LibraryFine(models.Model):
    _name = 'library.fine'
    _description = 'Library Fine'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_created desc'

    name = fields.Char('Fine Reference', compute='_compute_name', store=True)
    member_id = fields.Many2one('library.member', 'Member', required=True, tracking=True)
    borrowing_id = fields.Many2one('library.borrowing', 'Related Borrowing', tracking=True)
    amount = fields.Float('Amount', required=True, digits='Product Price', tracking=True)
    reason = fields.Selection([
        ('late_return', 'Late Return'),
        ('damage', 'Book Damage'),
        ('lost', 'Lost Book'),
        ('other', 'Other'),
    ], 'Reason', required=True, tracking=True)
    date_created = fields.Date('Date Created', default=fields.Date.today, required=True)
    date_paid = fields.Date('Date Paid', tracking=True)
    due_date = fields.Date('Due Date', compute='_compute_due_date', store=True)
    
    state = fields.Selection([
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('waived', 'Waived'),
        ('partial', 'Partially Paid'),
    ], 'Status', default='pending', tracking=True)
    
    paid_amount = fields.Float('Paid Amount', digits='Product Price', tracking=True)
    remaining_amount = fields.Float('Remaining Amount', compute='_compute_remaining_amount', store=True)
    
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('online', 'Online'),
        ('bank_transfer', 'Bank Transfer'),
    ], 'Payment Method')
    
    payment_reference = fields.Char('Payment Reference')
    notes = fields.Text('Notes')
    waived_reason = fields.Text('Waived Reason')
    processed_by = fields.Many2one('res.users', 'Processed By', default=lambda self: self.env.user)
    
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    @api.depends('member_id', 'reason', 'date_created')
    def _compute_name(self):
        for fine in self:
            if fine.member_id:
                fine.name = f"Fine - {fine.member_id.name} - {fine.reason} - {fine.date_created}"
            else:
                fine.name = "New Fine"

    @api.depends('date_created')
    def _compute_due_date(self):
        for fine in self:
            if fine.date_created:
                fine.due_date = fine.date_created + timedelta(days=30)  # 30 days to pay

    @api.depends('amount', 'paid_amount')
    def _compute_remaining_amount(self):
        for fine in self:
            fine.remaining_amount = fine.amount - fine.paid_amount

    @api.onchange('paid_amount')
    def _onchange_paid_amount(self):
        if self.paid_amount:
            if self.paid_amount >= self.amount:
                self.state = 'paid'
            elif self.paid_amount > 0:
                self.state = 'partial'
            else:
                self.state = 'pending'

    def action_mark_paid(self):
        self.paid_amount = self.amount
        self.date_paid = fields.Date.today()
        self.state = 'paid'
        self.message_post(body=f"Fine marked as paid: {self.amount}")

    def action_waive(self, reason):
        self.state = 'waived'
        self.waived_reason = reason
        self.message_post(body=f"Fine waived. Reason: {reason}")

    def action_partial_payment(self, amount, method, reference=None):
        if amount <= 0 or amount > self.remaining_amount:
            raise ValidationError("Invalid payment amount!")
        
        self.paid_amount += amount
        self.payment_method = method
        self.payment_reference = reference
        
        if self.paid_amount >= self.amount:
            self.state = 'paid'
            self.date_paid = fields.Date.today()
        else:
            self.state = 'partial'
        
        self.message_post(body=f"Partial payment received: {amount}")