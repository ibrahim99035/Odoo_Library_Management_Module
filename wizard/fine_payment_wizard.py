from odoo import models, fields, api
from odoo.exceptions import UserError

class FinePaymentWizard(models.TransientModel):
    _name = 'fine.payment.wizard'
    _description = 'Fine Payment Wizard'

    fine_id = fields.Many2one('library.fine', 'Fine', required=True)
    payment_amount = fields.Float('Payment Amount', required=True)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('online', 'Online'),
        ('bank_transfer', 'Bank Transfer'),
    ], 'Payment Method', required=True)
    payment_reference = fields.Char('Payment Reference')

    def action_pay_fine(self):
        if self.payment_amount <= 0:
            raise UserError('Payment amount must be positive.')
        if self.payment_amount > self.fine_id.remaining_amount:
            raise UserError('Payment exceeds remaining fine amount.')
        self.fine_id.paid_amount += self.payment_amount
        self.fine_id.payment_method = self.payment_method
        self.fine_id.payment_reference = self.payment_reference
        if self.fine_id.paid_amount >= self.fine_id.amount:
            self.fine_id.state = 'paid'
        else:
            self.fine_id.state = 'partial'
        return {'type': 'ir.actions.act_window_close'}